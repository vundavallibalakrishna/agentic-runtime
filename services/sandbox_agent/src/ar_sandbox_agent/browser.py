"""Drive a real Chromium page inside the sandbox with Playwright. Task: M40-T04b.

One browser context lives in this agent process, which is one sandbox's container, so a
page's cookies never reach another sandbox. The tools keep the names and shapes M37's
in-process browser used (``navigate``, ``snapshot``, ``click``, ``type``, ``press``,
``select``, ``hover``, ``scroll``, ``wait_for``) and add a real ``screenshot``; the runtime
keeps the navigation-approval and egress rules (M40-T04c). Playwright is present only in the
browser image, so it is imported lazily and a plain error is returned when it is absent.
Spec: docs/03-specs/12-sandbox-manager.md §7.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ar_common.sandboxkit import confine

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

BROWSER_TOOLS = frozenset(
    {
        "navigate",
        "snapshot",
        "click",
        "type",
        "press",
        "select",
        "hover",
        "scroll",
        "wait_for",
        "screenshot",
        "submit_form",
        "save_pdf",
        "download",
        "upload",
        "tabs",
        "new_tab",
        "switch_tab",
        "close_tab",
    }
)

_DEFAULT_SNAPSHOT_CHARS = 40000
_SMALL_SNAPSHOT_CHARS = 4000
_NAV_TIMEOUT_MS = 30000
_MAX_DOWNLOAD = 25 * 1024 * 1024

# Tag every visible interactive element with a stable ref and return the page outline.
_SNAPSHOT_JS = """
(maxChars) => {
  const sel = 'a,button,input,select,textarea,summary,[role=button],[role=link],'
    + '[role=tab],[role=menuitem],[role=checkbox],[role=switch],[onclick],'
    + '[contenteditable=""],[contenteditable=true]';
  const nodes = Array.from(document.querySelectorAll(sel));
  let i = 0; const elements = [];
  for (const el of nodes) {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    if (rect.width <= 0 || rect.height <= 0 || style.visibility === 'hidden'
        || style.display === 'none') continue;
    const ref = 'e' + (++i);
    el.setAttribute('data-ar-ref', ref);
    const value = (typeof el.value === 'string') ? el.value : '';
    let name = el.getAttribute('aria-label') || value || el.innerText
      || el.getAttribute('placeholder') || el.getAttribute('title') || '';
    name = name.trim().replace(/\\s+/g, ' ').slice(0, 120);
    elements.push({ref: ref, role: el.getAttribute('role') || el.tagName.toLowerCase(),
                   name: name});
  }
  const text = document.body
    ? document.body.innerText.replace(/[ \\t]+\\n/g, '\\n').slice(0, maxChars) : '';
  return {title: document.title, url: location.href, text: text, elements: elements};
}
"""


class _Session:
    """The one Playwright browser context for this sandbox, with its open tabs.

    Started on first use. One context per process (one per container) keeps a page's
    cookies off every other sandbox; the tabs are the pages of that context.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pw: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._active: Any = None

    async def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        from playwright.async_api import async_playwright  # noqa: PLC0415

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(args=["--no-sandbox"])

    async def _ensure(self) -> None:
        await self._ensure_browser()
        if self._context is None:
            self._context = await self._browser.new_context()
            self._active = await self._context.new_page()

    async def restore(self, storage_state: dict[str, object]) -> None:
        """Replace the context with a fresh, isolated one carrying the connection's state.

        Closing the old context first drops every earlier cookie and storage entry, so no
        prior sign-in bleeds into the restored one. The state arrives only on the trusted
        ``/admin/session`` channel, never from a model-callable tool (M40-T05c).
        """
        await self._ensure_browser()
        old = self._context
        self._context = await self._browser.new_context(storage_state=storage_state)
        self._active = await self._context.new_page()
        if old is not None:
            await old.close()

    async def context(self) -> Any:
        await self._ensure()
        return self._context

    async def page(self) -> Any:
        await self._ensure()
        if self._active is None or self._active.is_closed():
            self._active = await self._context.new_page()
        return self._active

    def set_active(self, page: Any) -> None:
        self._active = page


_SESSION = _Session()


async def restore_session(storage_state: dict[str, object], handle: str) -> dict[str, object]:
    """Load a connection's browser state into a fresh context. Trusted channel only.

    The caller is the sandbox-manager/runtime over ``/admin/session`` with the sandbox
    token; the state never comes from a model tool call and is never echoed back.
    """
    try:
        import playwright  # noqa: F401, PLC0415
    except ImportError:
        return {"status": "no_browser", "handle": handle}
    async with _SESSION._lock:
        await _SESSION.restore(storage_state)
    return {"status": "ready", "handle": handle}


async def export_session() -> dict[str, object]:
    """Return the active context's current browser state. Trusted channel only.

    The runtime re-seals this to the connection; it never passes through a model tool or
    result. With no started context there is nothing to save.
    """
    try:
        import playwright  # noqa: F401, PLC0415
    except ImportError:
        return {"status": "no_browser"}
    async with _SESSION._lock:
        context = _SESSION._context
        if context is None:
            return {"status": "empty"}
        state = await context.storage_state()
    return {"status": "ready", "storage_state": state}


async def scripted_login(spec: dict[str, object]) -> dict[str, object]:
    """Drive a scripted login in a fresh context. Trusted channel only; never the model.

    The field values (including the password) arrive on ``/admin/login`` with the sandbox
    token and are typed into the page, exactly as a person would. On success the new state
    is returned for the runtime to seal; an MFA or CAPTCHA marker returns ``needs_human``.
    """
    try:
        import playwright  # noqa: F401, PLC0415
    except ImportError:
        return {"status": "no_browser"}
    url = str(spec.get("url") or "")
    raw_steps = spec.get("steps")
    steps: list[Any] = raw_steps if isinstance(raw_steps, list) else []
    submit = str(spec.get("submit_selector") or "")
    success = str(spec.get("success_selector") or "")
    raw_mfa = spec.get("mfa_selectors")
    mfa: list[Any] = raw_mfa if isinstance(raw_mfa, list) else []
    async with _SESSION._lock:
        await _SESSION.restore({"cookies": [], "origins": []})
        page = await _SESSION.page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
            for step in steps:
                selector = str(step.get("selector") or "") if isinstance(step, dict) else ""
                value = str(step.get("value") or "") if isinstance(step, dict) else ""
                await page.locator(selector).fill(value, timeout=_NAV_TIMEOUT_MS)
            if submit:
                await page.locator(submit).click(timeout=_NAV_TIMEOUT_MS)
            with contextlib.suppress(Exception):
                await page.wait_for_load_state("networkidle", timeout=_NAV_TIMEOUT_MS)
        except Exception as exc:  # noqa: BLE001 - a login failure is reported, never raised
            return {"status": "failed", "reason": type(exc).__name__}
        for selector in mfa:
            if await page.locator(str(selector)).count() > 0:
                return {"status": "needs_human", "reason": "mfa"}
        if success and await page.locator(success).count() == 0:
            return {"status": "failed", "reason": "no_success_marker"}
        context = await _SESSION.context()
        return {"status": "ready", "storage_state": await context.storage_state()}


async def run_browser(name: str, arguments: dict[str, object]) -> dict[str, object]:
    """Dispatch one browser tool, or report that the browser is not installed."""
    try:
        import playwright  # noqa: F401, PLC0415
    except ImportError:
        return {
            "text": "this computer has no browser; use a browser template",
            "is_error": True,
            "code": "browser_unavailable",
        }
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"text": f"unknown tool {name}", "is_error": True, "code": "unknown_tool"}
    async with _SESSION._lock:
        try:
            page = await _SESSION.page()
            return await handler(page, arguments)
        except Exception as exc:  # noqa: BLE001 - any page error is reported, never raised
            return {
                "text": f"{type(exc).__name__}: {exc}",
                "is_error": True,
                "code": "browser_error",
            }


async def _snapshot_result(page: Any, max_chars: int) -> dict[str, object]:
    data = await page.evaluate(_SNAPSHOT_JS, max_chars)
    elements = data.get("elements", []) if isinstance(data, dict) else []
    lines = [str(data.get("title") or ""), str(data.get("url") or "")]
    lines.extend(f'- [{el["ref"]}] {el["role"]} "{el["name"]}"' for el in elements)
    lines.append("--- page text ---")
    lines.append(str(data.get("text") or ""))
    return {
        "text": "\n".join(line for line in lines if line is not None),
        "structured": {
            "title": data.get("title"),
            "url": data.get("url"),
            "elements": elements,
            "text": data.get("text"),
        },
        "is_error": False,
    }


async def _navigate(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    url = str(arguments.get("url") or "").strip()
    if not url:
        return {"text": "url is required", "is_error": True, "code": "validation_failed"}
    await page.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
    return await _snapshot_result(page, _snapshot_chars(arguments))


async def _snapshot(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    return await _snapshot_result(page, _snapshot_chars(arguments, _DEFAULT_SNAPSHOT_CHARS))


async def _click(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    await _locator(page, arguments).click(timeout=_NAV_TIMEOUT_MS)
    return await _snapshot_result(page, _SMALL_SNAPSHOT_CHARS)


async def _type(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    text = str(arguments.get("text") or "")
    await _locator(page, arguments).fill(text, timeout=_NAV_TIMEOUT_MS)
    return await _snapshot_result(page, _SMALL_SNAPSHOT_CHARS)


async def _press(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    key = str(arguments.get("key") or "Enter")
    await page.keyboard.press(key)
    return await _snapshot_result(page, _SMALL_SNAPSHOT_CHARS)


async def _select(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    value = str(arguments.get("value") or "")
    await _locator(page, arguments).select_option(value, timeout=_NAV_TIMEOUT_MS)
    return await _snapshot_result(page, _SMALL_SNAPSHOT_CHARS)


async def _hover(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    await _locator(page, arguments).hover(timeout=_NAV_TIMEOUT_MS)
    return await _snapshot_result(page, _SMALL_SNAPSHOT_CHARS)


async def _scroll(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    dy = _as_int(arguments.get("dy"), 600)
    dx = _as_int(arguments.get("dx"), 0)
    await page.mouse.wheel(dx, dy)
    return await _snapshot_result(page, _SMALL_SNAPSHOT_CHARS)


async def _wait_for(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    text = str(arguments.get("text") or "").strip()
    if text:
        await page.get_by_text(text).first.wait_for(timeout=_NAV_TIMEOUT_MS)
    else:
        await page.wait_for_load_state("networkidle", timeout=_NAV_TIMEOUT_MS)
    return await _snapshot_result(page, _snapshot_chars(arguments))


async def _submit_form(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    ref = str(arguments.get("ref") or "").strip()
    if ref:
        await page.evaluate(
            '(r) => { const el = document.querySelector(`[data-ar-ref="${r}"]`);'
            " const f = el && el.closest('form');"
            " if (f) { f.requestSubmit ? f.requestSubmit() : f.submit(); } }",
            ref,
        )
    else:
        await page.keyboard.press("Enter")
    # A JavaScript form may not trigger a navigation; a missed load is not an error.
    with contextlib.suppress(Exception):
        await page.wait_for_load_state("domcontentloaded", timeout=_NAV_TIMEOUT_MS)
    return await _snapshot_result(page, _SMALL_SNAPSHOT_CHARS)


async def _screenshot(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    full = arguments.get("full_page") is True
    png = await page.screenshot(full_page=full)
    encoded = base64.b64encode(png).decode("ascii")
    return {
        "text": f"captured a {len(png)}-byte screenshot",
        "structured": {"image_base64": encoded, "mime_type": "image/png", "bytes": len(png)},
        "is_error": False,
    }


async def _save_pdf(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    landscape = arguments.get("landscape") is True
    pdf = await page.pdf(print_background=True, landscape=landscape)
    return {
        "text": f"saved a {len(pdf)}-byte PDF of the page",
        "structured": {
            "file_base64": base64.b64encode(pdf).decode("ascii"),
            "filename": "page.pdf",
            "mime_type": "application/pdf",
            "bytes": len(pdf),
        },
        "is_error": False,
    }


async def _download(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    async with page.expect_download(timeout=_NAV_TIMEOUT_MS) as info:
        await _locator(page, arguments).click(timeout=_NAV_TIMEOUT_MS)
    download = await info.value
    path = await download.path()
    data = await asyncio.to_thread(Path(str(path)).read_bytes) if path else b""
    if len(data) > _MAX_DOWNLOAD:
        return {
            "text": f"the download is over {_MAX_DOWNLOAD // (1024 * 1024)} MiB",
            "is_error": True,
            "code": "validation_failed",
        }
    name = _safe_name(str(download.suggested_filename or "download"))
    return {
        "text": f"downloaded {name} ({len(data)} bytes)",
        "structured": {
            "file_base64": base64.b64encode(data).decode("ascii"),
            "filename": name,
            "mime_type": "application/octet-stream",
            "bytes": len(data),
        },
        "is_error": False,
    }


async def _upload(page: Any, arguments: dict[str, object]) -> dict[str, object]:
    root = Path(os.environ.get("AR_SANDBOX_ROOT", "/") or "/")
    target = confine(root, str(arguments.get("path") or ""))
    if not await asyncio.to_thread(target.is_file):
        return {
            "text": "file was not found in the workspace",
            "is_error": True,
            "code": "not_found",
        }
    await _locator(page, arguments).set_input_files(str(target), timeout=_NAV_TIMEOUT_MS)
    return {
        "text": f"attached {target.name} to the page",
        "structured": {"path": str(arguments.get("path") or ""), "name": target.name},
        "is_error": False,
    }


async def _tabs(_page: Any, _arguments: dict[str, object]) -> dict[str, object]:
    context = await _SESSION.context()
    active = await _SESSION.page()
    pages = list(context.pages)
    tabs: list[dict[str, object]] = []
    for index, open_page in enumerate(pages):
        tabs.append(
            {
                "index": index,
                "url": open_page.url,
                "title": await open_page.title(),
                "active": open_page is active,
            }
        )
    lines = [
        f"{'*' if tab['active'] else ' '} [{tab['index']}] {tab['title']} — {tab['url']}"
        for tab in tabs
    ]
    return {
        "text": "\n".join(lines) or "no tabs are open",
        "structured": {"tabs": tabs},
        "is_error": False,
    }


async def _new_tab(_page: Any, _arguments: dict[str, object]) -> dict[str, object]:
    context = await _SESSION.context()
    opened = await context.new_page()
    _SESSION.set_active(opened)
    return await _snapshot_result(opened, _SMALL_SNAPSHOT_CHARS)


async def _switch_tab(_page: Any, arguments: dict[str, object]) -> dict[str, object]:
    context = await _SESSION.context()
    pages = list(context.pages)
    index = _as_int(arguments.get("index"), -1)
    if index < 0 or index >= len(pages):
        return {"text": f"there is no tab {index}", "is_error": True, "code": "not_found"}
    target = pages[index]
    _SESSION.set_active(target)
    await target.bring_to_front()
    return await _snapshot_result(target, _SMALL_SNAPSHOT_CHARS)


async def _close_tab(_page: Any, arguments: dict[str, object]) -> dict[str, object]:
    context = await _SESSION.context()
    pages = list(context.pages)
    index = _as_int(arguments.get("index"), -1)
    if index < 0 or index >= len(pages):
        return {"text": f"there is no tab {index}", "is_error": True, "code": "not_found"}
    await pages[index].close()
    remaining = list(context.pages)
    _SESSION.set_active(remaining[-1] if remaining else None)
    return await _tabs(_page, arguments)


def _safe_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in name).strip("._")
    return cleaned or "download"


def _locator(page: Any, arguments: dict[str, object]) -> Any:
    ref = str(arguments.get("ref") or "").strip()
    return page.locator(f'[data-ar-ref="{ref}"]')


def _snapshot_chars(arguments: dict[str, object], default: int = _SMALL_SNAPSHOT_CHARS) -> int:
    return max(200, min(_as_int(arguments.get("max_chars"), default), _DEFAULT_SNAPSHOT_CHARS))


def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, (float, str)):
        try:
            return int(value)
        except TypeError, ValueError:
            return default
    return default


_HANDLERS: dict[str, Callable[[Any, dict[str, object]], Awaitable[dict[str, object]]]] = {
    "navigate": _navigate,
    "snapshot": _snapshot,
    "click": _click,
    "type": _type,
    "press": _press,
    "select": _select,
    "hover": _hover,
    "scroll": _scroll,
    "wait_for": _wait_for,
    "screenshot": _screenshot,
    "submit_form": _submit_form,
    "save_pdf": _save_pdf,
    "download": _download,
    "upload": _upload,
    "tabs": _tabs,
    "new_tab": _new_tab,
    "switch_tab": _switch_tab,
    "close_tab": _close_tab,
}
