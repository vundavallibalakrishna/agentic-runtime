"""Provider-specific paths and JSON bodies. The HTTP client stays generic."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from ar_domain.connectors.catalog import ConnectorDef, ToolDef

_PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_]+)\}")


def request_path(tool: ToolDef, arguments: dict[str, object]) -> str:
    """Fill `{name}` placeholders. A missing value raises KeyError."""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in arguments or arguments[name] in {None, ""}:
            raise KeyError(name)
        return quote(str(arguments[name]), safe="/")

    path = tool.path
    if tool.name in {"gcal_list_events", "gcal_create_event"}:
        calendar = str(arguments.get("calendar") or "primary")
        arguments = {**arguments, "calendar": calendar}
    if tool.name.startswith("sharepoint_search"):
        query = arguments.get("query")
        if query in {None, ""}:
            raise KeyError("query")
        return "/me/drive/root/search(q='" + quote(str(query), safe="") + "')"
    return _PLACEHOLDER.sub(replace, path)


def request_body(  # noqa: PLR0911
    connector: ConnectorDef, tool: ToolDef, arguments: dict[str, object]
) -> dict[str, object] | None:
    """JSON body for writes and a few reads. None means no body."""
    if tool.method in {"GET", "HEAD"} and tool.kind == "http":
        return None
    name = tool.name
    if name == "teams_post_message":
        return {"body": {"contentType": "text", "content": str(arguments.get("content") or "")}}
    if name == "gcal_find_free":
        calendar = str(arguments.get("calendar") or "primary")
        return {
            "timeMin": arguments.get("timeMin"),
            "timeMax": arguments.get("timeMax"),
            "items": [{"id": calendar}],
        }
    if name == "gcal_create_event":
        return {
            "summary": arguments.get("summary"),
            "start": {"dateTime": arguments.get("start")},
            "end": {"dateTime": arguments.get("end")},
        }
    if name == "m365cal_find_free":
        schedules = arguments.get("schedules")
        people = schedules if isinstance(schedules, list) else [str(schedules or "")]
        return {
            "schedules": people,
            "startTime": {"dateTime": arguments.get("start"), "timeZone": "UTC"},
            "endTime": {"dateTime": arguments.get("end"), "timeZone": "UTC"},
        }
    if name == "m365cal_create_event":
        return {
            "subject": arguments.get("subject"),
            "start": {"dateTime": arguments.get("start"), "timeZone": "UTC"},
            "end": {"dateTime": arguments.get("end"), "timeZone": "UTC"},
        }
    if name in {"jira_create_issue", "jira_update_issue"}:
        return _jira_issue(arguments, create=name == "jira_create_issue")
    if name == "jira_add_comment":
        return {"body": _adf(str(arguments.get("body") or ""))}
    if name == "confluence_write_page":
        return _confluence(arguments)
    if name == "notion_search":
        return {"query": str(arguments.get("query") or "")}
    if name == "notion_create_page":
        return {
            "parent": {"page_id": str(arguments.get("parent") or "")},
            "properties": {
                "title": {"title": [{"text": {"content": str(arguments.get("title") or "")}}]}
            },
        }
    if connector.slug == "slack" and tool.method == "POST":
        return {key: arguments[key] for key in tool.body if key in arguments}
    picked = {
        key: arguments[key]
        for key in tool.body
        if key in arguments and arguments[key] not in {None, ""}
    }
    return picked or None


def _adf(text: str) -> dict[str, object]:
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def _jira_issue(arguments: dict[str, object], *, create: bool) -> dict[str, object]:
    fields: dict[str, object] = {}
    if create:
        fields["project"] = {"key": str(arguments.get("project") or "")}
        fields["issuetype"] = {"name": "Task"}
    if arguments.get("summary"):
        fields["summary"] = str(arguments["summary"])
    if arguments.get("description"):
        fields["description"] = _adf(str(arguments["description"]))
    return {"fields": fields}


def _confluence(arguments: dict[str, object]) -> dict[str, object]:
    body: dict[str, object] = {
        "type": "page",
        "title": str(arguments.get("title") or ""),
        "body": {
            "storage": {
                "value": str(arguments.get("body") or ""),
                "representation": "storage",
            }
        },
    }
    if arguments.get("space"):
        body["space"] = {"key": str(arguments["space"])}
    if arguments.get("page_id"):
        body["version"] = {"number": 2}
    return body
