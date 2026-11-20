"""Tools that save a table query under a name, list saved queries and run one.

A saved query is run again against the file each time; no result is kept. Every result
says plainly whether the query was saved or run, so a reply cannot claim more than
happened. Saving with a file runs the statement once on it as a check and returns the
rows and the count, so the person can read what it finds before it goes for sign-off.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_domain.rows import as_int
from ar_domain.spreadsheet.engine import SheetQueryError
from ar_domain.spreadsheet.saved import CheckRun, SavedQueryBook, SignOff
from ar_domain.tools.sql_guard import SqlRejected

if TYPE_CHECKING:
    from typing import Any as Store

_HASH_SHOWN = 12


def save_query(store: Store, arguments: dict[str, object]) -> dict[str, object]:
    """Run ``general.save_query``.

    With ``path`` or ``paths`` the statement is run once on those files before it is
    saved, through the same guard and engine as ``general.query_table``. A statement that
    fails is not saved. The rows and count of that check run come back with the result.
    """
    from ar_domain.tools.analysis import (  # noqa: PLC0415
        _checked,
        _error,
        _ok,
        _query_result,
        _requested_paths,
        run_statement,
    )

    owner = _owner(arguments)
    if owner is None:
        return _error("validation_failed", "Not saved. This call has no signed-in person.")
    tenant_id, user_id = owner
    name = str(arguments.get("name") or "").strip()
    sql = str(arguments.get("sql") or "").strip()
    if not name or not sql:
        return _error("validation_failed", "Not saved. name and sql are both required.")
    book = SavedQueryBook(store)
    paths = _requested_paths(arguments)
    found: tuple[list[str], list[list[object]]] | None = None
    check: CheckRun | None = None
    try:
        checked = _checked(store, arguments, sql)
        # Refuse a save that cannot succeed before the statement reads any file.
        book.savable(tenant_id, name=name, sql=sql)
        if paths:
            columns, rows, truncated = run_statement(store, arguments, checked)
            found = (columns, rows)
            check = CheckRun(paths=tuple(paths), rows=len(rows), truncated=truncated)
        row, created = book.save(
            tenant_id,
            user_id,
            name=name,
            sql=sql,
            description=str(arguments.get("description") or "").strip(),
            checked=check,
        )
        state = book.sign_off(tenant_id, row)
    except (SqlRejected, SheetQueryError, ValidationFailedError, NotFoundError) as exc:
        return _error(*_not_saved(exc))
    label = _label(row)
    opening = (
        f"Saved {label}."
        if created
        else f"Nothing new was saved: {label} already holds this statement and description."
    )
    saved: dict[str, object] = {
        "kind": "saved_query",
        "saved": created,
        **_identity(row),
        "sql": row["sql"],
        "description": row["description"],
        "signoff": _signoff(state),
    }
    standing = f"{opening} {_standing(state, row)}"
    if check is None or found is None:
        return _ok(f"{standing} {_UNCHECKED}", saved)
    # The same preview and text a query gives, so the chat shows the rows as a table.
    shown = _query_result(checked, found[0], found[1], truncated=check.truncated)
    return _with_check(shown, saved, check, f"{standing}\n{_checked_note(check, state, row)}")


def _not_saved(exc: Exception) -> tuple[str, str]:
    """The error code and the words for a save that was refused. Nothing was written."""
    if isinstance(exc, SqlRejected):
        return "sql_rejected", f"Not saved. The statement was refused: {exc.reason}"
    if isinstance(exc, SheetQueryError):
        return "validation_failed", f"Not saved. The statement did not run: {exc.reason}"
    return "validation_failed", f"Not saved. {exc}"


_UNCHECKED = (
    "The statement was not checked against a file, so no rows and no count are shown. "
    "Pass path or paths when saving to check it."
)


def _with_check(
    shown: dict[str, object], saved: dict[str, object], check: CheckRun, opening: str
) -> dict[str, object]:
    """A query result for the check run, carrying everything a save result carries."""
    shown["text"] = f"{opening}\n{shown['text']}"
    structured = shown["structured"]
    if isinstance(structured, dict) and isinstance(structured.get("presentation"), dict):
        structured["presentation"].update(
            {
                **{key: value for key, value in saved.items() if key != "kind"},
                "check": {
                    "paths": list(check.paths),
                    "rows": check.rows,
                    "truncated": check.truncated,
                },
            }
        )
    return shown


def list_saved_queries(store: Store, arguments: dict[str, object]) -> dict[str, object]:
    """Run ``general.list_saved_queries``."""
    from ar_domain.tools.analysis import _error, _ok  # noqa: PLC0415

    owner = _owner(arguments)
    if owner is None:
        return _error("validation_failed", "This call has no signed-in person.")
    tenant_id, _user_id = owner
    book = SavedQueryBook(store)
    try:
        listed = [(row, book.sign_off(tenant_id, row)) for row in book.latest(tenant_id)]
    except ValidationFailedError as exc:
        return _error("validation_failed", str(exc))
    if not listed:
        return _ok(
            "No query has been saved in this workspace.",
            {"kind": "table", "columns": _LIST_COLUMNS, "rows": [], "truncated": False},
        )
    rows: list[list[object]] = [
        [
            row["name"],
            row["version"],
            row["description"],
            state.status,
            str(row.get("created_at") or ""),
        ]
        for row, state in listed
    ]
    lines = [
        f"{row['name']} (version {row['version']}, sign-off: {state.status}): "
        f"{row['description'] or 'no description'}\n  {row['sql']}"
        for row, state in listed
    ]
    return _ok(
        "Saved queries, newest version of each:\n" + "\n".join(lines),
        {"kind": "table", "columns": _LIST_COLUMNS, "rows": rows, "truncated": False},
    )


def run_saved_query(store: Store, arguments: dict[str, object]) -> dict[str, object]:
    """Run ``general.run_saved_query``: the stored statement, against the file as it is now."""
    from ar_domain.tools.analysis import (  # noqa: PLC0415
        _checked,
        _error,
        _query_result,
        run_statement,
    )

    owner = _owner(arguments)
    if owner is None:
        return _error("validation_failed", "Not run. This call has no signed-in person.")
    tenant_id, user_id = owner
    book = SavedQueryBook(store)
    try:
        name, version = _wanted(arguments)
        row = book.get(tenant_id, name, version)
        state = book.sign_off(tenant_id, row)
        if not state.runnable:
            return _error("signoff_required", _refusal(book, tenant_id, row, state))
    except NotFoundError as exc:
        known = ", ".join(str(item["name"]) for item in book.latest(tenant_id)) or "none"
        return _error("validation_failed", f"Not run. {exc}. The saved queries are: {known}.")
    except ValidationFailedError as exc:
        return _error("validation_failed", f"Not run. {exc}")
    checked = _checked(store, arguments, str(row["sql"]))
    columns, rows, truncated = run_statement(store, arguments, checked)
    book.record_run(tenant_id, user_id, row, rows=len(rows))
    result = _query_result(checked, columns, rows, truncated=truncated)
    result["text"] = f"Ran {_label(row)}. {_standing(state, row)}\n{result['text']}"
    structured = result["structured"]
    if isinstance(structured, dict) and isinstance(structured.get("presentation"), dict):
        structured["presentation"]["saved_query"] = {**_identity(row), "signoff": _signoff(state)}
    return result


_LIST_COLUMNS = ["name", "version", "description", "sign_off", "saved_at"]


def _owner(arguments: dict[str, object]) -> tuple[uuid.UUID, uuid.UUID] | None:
    tenant_id = arguments.get("_tenant_id")
    user_id = arguments.get("_user_id")
    if isinstance(tenant_id, uuid.UUID) and isinstance(user_id, uuid.UUID):
        return tenant_id, user_id
    return None


def _wanted(arguments: dict[str, object]) -> tuple[str, int | None]:
    """The name and version a run asks for. No version means the newest."""
    name = str(arguments.get("name") or "").strip()
    if not name:
        raise ValidationFailedError("name is required.")
    raw = arguments.get("version")
    if raw is None:
        return name, None
    if isinstance(raw, str) and raw.strip().isdigit():
        raw = int(raw.strip())
    version = as_int(raw, 0)
    if version < 1:
        raise ValidationFailedError("version must be a whole number from 1.")
    return name, version


def _label(row: dict[str, object]) -> str:
    digest = str(row.get("content_hash") or "")[:_HASH_SHOWN]
    return f"the query {row['name']} as version {row['version']} (hash {digest})"


def _identity(row: dict[str, object]) -> dict[str, object]:
    return {
        "name": row["name"],
        "version": row["version"],
        "content_hash": row["content_hash"],
    }


def _signoff(state: SignOff) -> dict[str, object]:
    return {
        "required": state.required,
        "status": state.status,
        "queue": state.queue_name,
        "approved_by": list(state.approvers),
        "approved_at": state.approved_at.isoformat() if state.approved_at else None,
        "review_item_id": str(state.review_item_id) if state.review_item_id else None,
    }


def _who(state: SignOff) -> str:
    role = f" with the role {state.role}" if state.role else ""
    return (
        f"Someone{role} who may decide reviews in the queue {state.queue_name}, other than "
        "the person who saved it, must approve it on the Reviews screen."
    )


def _standing(state: SignOff, row: dict[str, object]) -> str:
    """One or two sentences on whether this version may run, for the model to repeat."""
    if not state.required:
        return (
            "No sign-off is configured for saved queries in this workspace, so this version "
            "can be run at once and nobody has approved it."
        )
    if state.status == "signed":
        when = state.approved_at.isoformat() if state.approved_at else "an unrecorded time"
        return f"Approved by {', '.join(state.approvers) or 'a reviewer'} at {when}."
    if state.status == "rejected":
        return (
            f"Version {row['version']} was rejected in the queue {state.queue_name} and cannot "
            "run. Save an amended statement to make a new version."
        )
    if state.status == "unrequested":
        return (
            f"Version {row['version']} has not been sent for sign-off, which this workspace "
            "requires. Call save_query again with the same name, sql and description to send "
            "it. It cannot run until it is approved."
        )
    return (
        f"Sign-off is required before it may run, and it has not been approved yet "
        f"(status {state.status}). {_who(state)} It cannot be run until then."
    )


def _checked_note(check: CheckRun, state: SignOff, row: dict[str, object]) -> str:
    """What the check run made while saving found, and that it is not a run of the version."""
    count = f"at least {check.rows}" if check.truncated else str(check.rows)
    noun = "row" if check.rows == 1 and not check.truncated else "rows"
    cut = (
        f" Only the first {check.rows} rows are counted; the statement returns more."
        if check.truncated
        else ""
    )
    later = (
        " It can be run again on any file with run_saved_query."
        if state.runnable
        else f" Version {row['version']} cannot be run again until it is signed."
    )
    return (
        f"Check run on {', '.join(check.paths)}, made once while saving: the statement "
        f"returned {count} {noun}.{cut} The rows below are from that check run, "
        f"not from a run of the saved version.{later}"
    )


def _refusal(
    book: SavedQueryBook, tenant_id: uuid.UUID, row: dict[str, object], state: SignOff
) -> str:
    signed = [
        str(item["version"])
        for item in book.versions(tenant_id, str(row["name"]))
        if item["id"] != row["id"] and book.sign_off(tenant_id, item).status == "signed"
    ]
    other = (
        f" Approved versions that can run now: {', '.join(signed)}. Pass version to run one."
        if signed
        else ""
    )
    return f"Not run. {_standing(state, row)}{other}"
