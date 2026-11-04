"""JSON bodies for the second connector batch."""

from __future__ import annotations

import orjson

_UNSET = object()


def batch_body(name: str, arguments: dict[str, object]) -> object:  # noqa: PLR0911
    """Return a body, None, or the unset marker when this tool is generic."""
    if name in {"servicenow_create_incident", "servicenow_update_incident"}:
        return _fields(arguments, ("short_description", "description", "urgency", "category"))
    if name in {"servicenow_create_change", "servicenow_update_change"}:
        return _fields(arguments, ("short_description", "description", "category", "type"))
    if name in {"salesforce_create_record", "salesforce_update_record"}:
        return _json_object(arguments.get("fields"))
    if name == "zendesk_create_ticket":
        return {
            "ticket": {
                "subject": str(arguments.get("subject") or ""),
                "comment": {"body": str(arguments.get("comment") or "")},
            }
        }
    if name == "zendesk_add_comment":
        return {"ticket": {"comment": {"body": str(arguments.get("comment") or "")}}}
    if name in {"hubspot_search_contacts", "hubspot_search_companies"}:
        body: dict[str, object] = {"query": str(arguments.get("query") or ""), "limit": 10}
        if arguments.get("after"):
            body["after"] = str(arguments["after"])
        return body
    if name in {"hubspot_create_contact", "hubspot_update_contact"}:
        properties = _fields(arguments, ("email", "firstname", "lastname"))
        return {"properties": properties}
    if name == "gcp_get_iam_policy":
        return {}
    return _UNSET


def is_unset(value: object) -> bool:
    return value is _UNSET


def _fields(arguments: dict[str, object], names: tuple[str, ...]) -> dict[str, object]:
    return {
        key: arguments[key]
        for key in names
        if key in arguments and arguments[key] not in {None, ""}
    }


def _json_object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            loaded = orjson.loads(value)
        except orjson.JSONDecodeError:
            return {}
        if isinstance(loaded, dict):
            return loaded
    return {}
