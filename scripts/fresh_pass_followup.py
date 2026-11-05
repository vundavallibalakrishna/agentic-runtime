# ruff: noqa
from __future__ import annotations
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("AR_PROOF_API", "http://127.0.0.1:18131")
import scripts.m31_followup as follow

follow.ALIAS = "qwenfresh"
# rewrite issue/approval path that writes to /tmp/m31-proof
import inspect, textwrap

src = textwrap.dedent(inspect.getsource(follow.main))
src = src.replace("/tmp/m31-proof/followup.json", "/tmp/fresh-pass-proof/followup.json")
ns = dict(vars(follow))
exec(compile(src, "<fresh:followup>", "exec"), ns)
follow.main = ns["main"]
follow.main()
