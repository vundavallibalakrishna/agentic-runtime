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


class _Found:
    """A page locator that matched ``count`` elements and records what was done to it."""

    def __init__(self, count: int) -> None:
        self._count = count
        self.done: list[str] = []

    async def count(self) -> int:
        return self._count

    async def click(self, **_kw: object) -> None:
        self.done.append("click")

    async def fill(self, text: str, **_kw: object) -> None:
        self.done.append(f"fill:{text}")


class _Page:
    """A page that knows one element, ``e1``."""

    def __init__(self) -> None:
        self.asked: list[str] = []
        self.element = _Found(1)

    def locator(self, selector: str) -> _Found:
        self.asked.append(selector)
        return self.element if '"e1"' in selector else _Found(0)


def test_a_tool_that_names_no_element_is_refused_at_once() -> None:
    import pytest

    from ar_sandbox_agent.browser import NoElementError, _locator

    page = _Page()
    with pytest.raises(NoElementError, match="ref is required"):
        asyncio.run(_locator(page, {}))
    # Nothing was looked up, so nothing waited.
    assert page.asked == []
    with pytest.raises(NoElementError, match="no element e9 is on this page"):
        asyncio.run(_locator(page, {"ref": "e9"}))
    found = asyncio.run(_locator(page, {"ref": "e1"}))
    assert found is page.element


def test_click_and_type_act_on_the_named_element(monkeypatch: object) -> None:
    from ar_sandbox_agent import browser

    async def snapshot(_page: object, _chars: int) -> dict[str, object]:
        return {"text": "page", "is_error": False}

    monkeypatch.setattr(browser, "_snapshot_result", snapshot)  # type: ignore[attr-defined]
    page = _Page()
    assert asyncio.run(browser._click(page, {"ref": "e1"}))["text"] == "page"
    assert asyncio.run(browser._type(page, {"ref": "e1", "text": "hello"}))["text"] == "page"
    assert page.element.done == ["click", "fill:hello"]
