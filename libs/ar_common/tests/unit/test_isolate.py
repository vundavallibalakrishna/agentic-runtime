"""The sandbox must not see platform secrets or the host filesystem."""

import os
import sys
from pathlib import Path

from ar_common.isolate import isolation_mode, run_isolated, scrubbed_env


def test_scrubbed_env_drops_the_parent_secret(monkeypatch: object) -> None:
    del monkeypatch
    os.environ["AR_CERT_LLM_API_KEY"] = "sentinel-secret-value"
    env = scrubbed_env(Path("/workspace"))
    assert "AR_CERT_LLM_API_KEY" not in env
    assert "sentinel-secret-value" not in " ".join(env.values())


def test_namespace_hides_the_host_and_blocks_network(tmp_path: Path) -> None:
    root = tmp_path / "run"
    script = root / "workspace"
    script.mkdir(parents=True)
    (script / "_agent.py").write_text(
        "import os\n"
        "print('key', 'AR_CERT_LLM_API_KEY' in os.environ)\n"
        "print('passwd', os.path.exists('/etc/passwd'))\n"
        "print('mode-file', os.path.exists('/workspace/_agent.py'))\n"
        "try:\n"
        "    import socket\n"
        "    socket.create_connection(('1.1.1.1', 53), 2)\n"
        "    print('net open')\n"
        "except Exception:\n"
        "    print('net closed')\n",
        encoding="utf-8",
    )
    os.environ["AR_CERT_LLM_API_KEY"] = "sentinel-secret-value"
    guest = (
        "/workspace/_agent.py"
        if isolation_mode() == "namespace"
        else str(root / "workspace" / "_agent.py")
    )
    result = run_isolated(
        root,
        [sys.executable, "-I", guest],
        timeout=15,
        network=False,
    )
    assert "sentinel-secret-value" not in result.stdout
    assert "key False" in result.stdout
    if isolation_mode() == "namespace":
        assert result.mode == "namespace"
        assert "passwd False" in result.stdout
        assert "net closed" in result.stdout
        assert not Path("/etc/passwd-ar-breakout").exists()
    else:
        assert result.mode == "process"
        assert result.exit_code == 0
