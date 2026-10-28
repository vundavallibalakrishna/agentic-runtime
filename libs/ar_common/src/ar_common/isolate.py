"""Run a command with a scrubbed environment and, when the kernel allows, a private root.

The namespace driver bind-mounts the interpreter and the per-run workspace, then
pivots the root so the host filesystem, platform secrets and the database are
not mounted. Network stays in a fresh net namespace unless the caller enables
it. A kernel that refuses user namespaces falls back to a scrubbed subprocess
in the workspace directory. That fallback is not a security boundary.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ar_common.sandboxkit import truncate_output


class _Cache:
    mode: str | None = None
    helper: Path | None = None


_HELPER = r"""
import ctypes
import os
import resource
import sys

root, network, prefixes, timeout_s, max_file = sys.argv[1:6]
argv = sys.argv[6:]
libc = ctypes.CDLL(None, use_errno=True)
MS_BIND = 4096


def mount(source, target, fstype, flags=0):
    kind = None if fstype is None else fstype.encode()
    result = libc.mount(source.encode(), target.encode(), kind, flags, None)
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), target)


os.makedirs(root + "/old", exist_ok=True)
for name in ("usr", "bin", "lib", "lib64", "proc", "tmp", "dev", "workspace", "etc"):
    os.makedirs(root + "/" + name, exist_ok=True)
mount(root, root, None, MS_BIND)
for source, name in (("/usr", "usr"), ("/bin", "bin"), ("/lib", "lib"), ("/lib64", "lib64")):
    if os.path.isdir(source):
        mount(source, root + "/" + name, None, MS_BIND)
for prefix in prefixes.split(":") if prefixes else []:
    if not prefix or prefix.startswith(("/usr", "/lib", "/bin")):
        continue
    target = root + prefix
    os.makedirs(target, exist_ok=True)
    mount(prefix, target, None, MS_BIND)
mount("proc", root + "/proc", "proc", 0)
mount("tmpfs", root + "/tmp", "tmpfs", 0)
mount("tmpfs", root + "/dev", "tmpfs", 0)
for node in ("null", "zero", "urandom"):
    source = "/dev/" + node
    if os.path.exists(source):
        dest = root + "/dev/" + node
        open(dest, "ab").close()
        mount(source, dest, None, MS_BIND)
if network == "1":
    for item in ("ssl",):
        source = "/etc/" + item
        if os.path.isdir(source):
            os.makedirs(root + source, exist_ok=True)
            mount(source, root + source, None, MS_BIND)
    for item in ("resolv.conf", "hosts", "nsswitch.conf"):
        source = "/etc/" + item
        if os.path.isfile(source):
            dest = root + source
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "ab").close()
            mount(source, dest, None, MS_BIND)
seconds = max(1, int(timeout_s))
resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds + 1))
file_cap = max(1024, int(max_file))
resource.setrlimit(resource.RLIMIT_FSIZE, (file_cap, file_cap))
os.chdir(root)
if libc.syscall(155, b".", b"old") != 0:
    error = ctypes.get_errno()
    raise OSError(error, "pivot_root " + os.strerror(error))
libc.umount2(b"/old", 2)
os.chdir("/workspace")
os.environ["HOME"] = "/workspace"
os.environ["TMPDIR"] = "/tmp"
os.environ["SANDBOX_WORKSPACE"] = "/workspace"
os.execv(argv[0], argv)
"""


@dataclass(frozen=True, slots=True)
class IsolatedRun:
    """One finished command."""

    exit_code: int
    stdout: str
    stderr: str
    truncated: bool
    mode: str


def isolation_mode() -> str:
    """``namespace`` when a private root can be built, otherwise ``process``."""
    if _Cache.mode is None:
        _Cache.mode = "namespace" if _probe() else "process"
    return _Cache.mode


def scrubbed_env(workspace: Path) -> dict[str, str]:
    """Environment for a child. Platform secrets and the parent environment stay out."""
    path = os.environ.get("PATH", "/usr/bin:/bin")
    exe_dir = str(Path(sys.executable).resolve().parent)
    if exe_dir not in path.split(":"):
        path = f"{exe_dir}:{path}"
    home = "/workspace" if isolation_mode() == "namespace" else str(workspace)
    temporary = home if isolation_mode() == "namespace" else str(workspace.parent / "tmp")
    return {
        "PATH": path,
        "HOME": home,
        "TMPDIR": temporary,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "SANDBOX_WORKSPACE": home,
    }


def run_isolated(
    root: Path,
    argv: list[str],
    *,
    timeout: int,
    network: bool,
    max_file_bytes: int = 1_048_576,
) -> IsolatedRun:
    """Run ``argv``. ``network`` is ignored by the process fallback."""
    workspace = root / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    env = scrubbed_env(workspace)
    if isolation_mode() == "namespace":
        return _namespace(
            root, argv, env, timeout=timeout, network=network, max_file_bytes=max_file_bytes
        )
    return _process(workspace, argv, env, timeout=timeout)


def _probe() -> bool:
    binary = shutil.which("unshare")
    if binary is None:
        return False
    try:
        result = subprocess.run(  # noqa: S603
            [
                binary,
                "--user",
                "--map-root-user",
                "--mount",
                "--pid",
                "--fork",
                "--net",
                "--propagation",
                "private",
                "true",
            ],
            check=False,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _prefixes() -> str:
    found: list[str] = []
    exe = Path(sys.executable).resolve()
    candidates = [Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve(), exe.parent]
    for path in candidates:
        text = str(path)
        if text in {"/", "/usr", "/usr/bin", "/bin", "/lib", "/lib64"}:
            continue
        if text.startswith(("/usr/", "/lib/", "/bin/")):
            continue
        if text not in found:
            found.append(text)
    return ":".join(found)


def _helper() -> Path:
    if _Cache.helper is None or not _Cache.helper.is_file():
        path = Path(tempfile.gettempdir()) / "ar-isolate-helper.py"
        path.write_text(_HELPER, encoding="utf-8")
        _Cache.helper = path
    return _Cache.helper


def _namespace(
    root: Path,
    argv: list[str],
    env: dict[str, str],
    *,
    timeout: int,
    network: bool,
    max_file_bytes: int,
) -> IsolatedRun:
    binary = shutil.which("unshare") or "unshare"
    command = [
        binary,
        "--user",
        "--map-root-user",
        "--mount",
        "--pid",
        "--fork",
        "--propagation",
        "private",
    ]
    if not network:
        command.append("--net")
    command.extend(
        [
            sys.executable,
            str(_helper()),
            str(root),
            "1" if network else "0",
            _prefixes(),
            str(max(1, timeout)),
            str(max_file_bytes),
            *argv,
        ]
    )
    return _spawn(command, env, cwd=root / "workspace", timeout=timeout, mode="namespace")


def _process(
    workspace: Path, argv: list[str], env: dict[str, str], *, timeout: int
) -> IsolatedRun:
    return _spawn(argv, env, cwd=workspace, timeout=timeout, mode="process")


def _spawn(
    command: list[str], env: dict[str, str], *, cwd: Path, timeout: int, mode: str
) -> IsolatedRun:
    proc = subprocess.Popen(  # noqa: S603
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=max(1, timeout) + 2)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        text_out, _text_err, _truncated = truncate_output(out or b"", err or b"")
        note = _text_err or f"timed out after {timeout}s"
        return IsolatedRun(124, text_out, note, True, mode)
    text_out, text_err, truncated = truncate_output(out or b"", err or b"")
    return IsolatedRun(proc.returncode or 0, text_out, text_err, truncated, mode)
