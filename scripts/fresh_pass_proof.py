# ruff: noqa
"""Fresh-pass live runner. Local only; never commit secrets."""

from __future__ import annotations

import os
import sys
import textwrap
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("AR_PROOF_API", "http://127.0.0.1:18131")
os.environ.setdefault("M31_ROOT", "/tmp/fresh-pass-proof")
os.environ.setdefault(
    "M31_DSN",
    "postgresql://ar_owner:ar_owner@127.0.0.1:5433/agentic_runtime",
)

import scripts.m31_proof as proof  # noqa: E402

proof.PDF = ROOT / "docs/architecture/agentic-runtime-architecture.pdf"
proof.ROOT = Path(os.environ["M31_ROOT"])
proof.DSN = os.environ["M31_DSN"]
proof.BASE = os.environ["AR_PROOF_API"]
proof.ALIAS = "qwenfresh"

REPLACEMENTS = [
    ("DeepInfra M31", "DeepInfra Fresh"),
    ("qwenm31", "qwenfresh"),
    ("M31 certification probe", "Fresh-pass probe Nov 5"),
    (
        "Created by the M31 certification. Safe to close.",
        "Created by the Nov 5 fresh-pass. Safe to close.",
    ),
    ('"slug": "m31"', '"slug": "fresh"'),
    ('"name": "M31"', '"name": "Fresh"'),
    ("m31@example.com", "fresh@example.com"),
    ("m31-repair-", "fresh-repair-"),
    ("m31-shell", "fresh-shell"),
    ("m31 workspace note", "fresh workspace note"),
    ('"text": "fresh workspace note"', '"content": "fresh workspace note"'),
    (
        '{"path": "/workspace/note.txt", "text": "fresh workspace note"}',
        '{"path": "/workspace/note.txt", "content": "fresh workspace note"}',
    ),
]


def _rewrite(fn):
    src = textwrap.dedent(inspect.getsource(fn))
    for old, new in REPLACEMENTS:
        src = src.replace(old, new)
    if fn.__name__ == "_tools":
        src = src.replace(
            '"httpbin.org",',
            '"httpbin.org",\n                        "example.com",',
        )
        # schema uses content not text
        src = src.replace(
            '{"path": "/workspace/note.txt", "text": "fresh workspace note"}',
            '{"path": "/workspace/note.txt", "content": "fresh workspace note"}',
        )
    ns = dict(vars(proof))
    exec(compile(src, f"<fresh:{fn.__name__}>", "exec"), ns)
    return ns[fn.__name__]


for name in (
    "_setup_model",
    "_connectors",
    "_identity",
    "_tools",
    "_chat",
    "_documents",
    "_knowledge",
    "_orchestration",
    "_external",
    "_publish",
    "_budget",
):
    if hasattr(proof, name):
        setattr(proof, name, _rewrite(getattr(proof, name)))

# Force _chat default alias by wrapping
_orig_chat = proof._chat


def _chat(client, agent_id, text, *, alias=proof.ALIAS):
    return _orig_chat(client, agent_id, text, alias=alias)


proof._chat = _chat

if not proof.PDF.is_file():
    raise SystemExit(f"missing PDF at {proof.PDF}")

print(
    f"fresh-pass proof api={proof.BASE} dsn_host_port=5433 pdf={proof.PDF.name} alias={proof.ALIAS}",
    flush=True,
)
proof.main()
