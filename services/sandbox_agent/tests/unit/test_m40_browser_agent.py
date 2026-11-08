"""The agent's browser dispatch and helpers. Task: M40-T04b.

No Chromium here: these cover the pure parts and the not-installed path. Driving a real
page is the docker-gated integration test.
"""

from __future__ import annotations

import asyncio

from ar_sandbox_agent.browser import (
    BROWSER_TOOLS,
    _as_int,
    _snapshot_chars,
    run_browser,
)


def test_browser_tools_cover_the_m37_surface() -> None:
    for name in ("navigate", "snapshot", "click", "type", "press", "scroll", "screenshot"):
        assert name in BROWSER_TOOLS


def test_browser_tools_include_the_file_flows() -> None:
    for name in ("save_pdf", "download", "upload", "submit_form"):
        assert name in BROWSER_TOOLS


def test_browser_tools_include_tabs() -> None:
    for name in ("tabs", "new_tab", "switch_tab", "close_tab"):
        assert name in BROWSER_TOOLS


def test_as_int_rejects_bool_and_bad_values() -> None:
    assert _as_int(True, 7) == 7
    assert _as_int(5, 7) == 5
    assert _as_int("12", 7) == 12
    assert _as_int("x", 7) == 7
    assert _as_int(None, 7) == 7


def test_snapshot_chars_clamps() -> None:
    assert _snapshot_chars({"max_chars": 10}) == 200  # floor
    assert _snapshot_chars({"max_chars": 10**9}) == 40000  # ceiling
    assert _snapshot_chars({}, 4000) == 4000


def test_an_unknown_browser_tool_is_reported() -> None:
    # 'navigate' is known; 'warp' is not. Either the browser is absent (no Chromium in the
    # unit env) or the tool is unknown — both are clean, non-raising errors.
    result = asyncio.run(run_browser("warp", {}))
    assert result["is_error"] is True
    assert result["code"] in {"unknown_tool", "browser_unavailable"}
