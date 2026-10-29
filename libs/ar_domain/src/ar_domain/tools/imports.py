"""OpenAPI import and tools described in plain language."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from ar_common.errors import ArError, ValidationFailedError
from ar_domain.tools.describe import compile_description
from ar_domain.tools.http_tools import fetch_document
from ar_domain.tools.openapi_import import (
    OpenApiError,
    index_operations,
    load_document,
    require_openapi3,
    server_url,
)
from ar_domain.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_MAX_SELECTED = 40


class ToolImporter:
    def __init__(self, store: Any) -> None:
        self.store = store
        self.registry = ToolRegistry(store)

    def preview_openapi(self, body: dict[str, object]) -> dict[str, object]:
        document = self._document(body)
        try:
            listed = index_operations(document)
        except OpenApiError as exc:
            raise ValidationFailedError(exc.reason) from exc
        listed["base_url"] = str(body.get("base_url") or "") or server_url(
            document, str(body.get("url") or "")
        )
        return listed

    def import_openapi(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        document = self._document(body)
        try:
            require_openapi3(document)
            listed = index_operations(document, limit=10_000)
        except OpenApiError as exc:
            raise ValidationFailedError(exc.reason) from exc
        operations = listed.get("operations")
        rows = operations if isinstance(operations, list) else []
        selected = body.get("operations")
        chosen = [str(item) for item in selected] if isinstance(selected, list) else []
        if not chosen and len(rows) > _MAX_SELECTED:
            raise ValidationFailedError(
                f"this spec has {len(rows)} operations. Select at most {_MAX_SELECTED}."
            )
        if len(chosen) > _MAX_SELECTED:
            raise ValidationFailedError(f"select at most {_MAX_SELECTED} operations")
        if not chosen:
            chosen = [str(item.get("operation_id")) for item in rows if isinstance(item, dict)]
        base = str(body.get("base_url") or "") or server_url(document, str(body.get("url") or ""))
        if not base.startswith(("http://", "https://")):
            raise ValidationFailedError("baseUrl is required when the document has no server URL")
        host = urlparse(base).hostname or ""
        slug = str(body.get("slug") or "")
        connection = str(body.get("connection") or "")
        created = self.registry.create_server(
            actor,
            {
                "slug": slug,
                "name": str(body.get("name") or slug),
                "description": str(body.get("description") or "Imported from an OpenAPI document"),
                "kind": "openapi",
                "version": {
                    "version": "1.0.0",
                    "config": {
                        "source": "openapi",
                        "base_url": base,
                        "connection": connection,
                        "allow_hosts": [host] if host else [],
                        "spec": document,
                        "openapi": {"operations": chosen},
                    },
                },
            },
        )
        self._drop_spec(created)
        self._publish(actor, created)
        return self.registry.get_server(actor, uuid.UUID(str(created["id"])))

    def preview_description(self, body: dict[str, object]) -> dict[str, object]:
        return compile_description(body)

    def save_description(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        definition = compile_description(body)
        host = urlparse(str(definition["url"])).hostname or ""
        slug = str(body.get("slug") or definition["name"])
        created = self.registry.create_server(
            actor,
            {
                "slug": slug,
                "name": str(body.get("title") or definition["title"]),
                "description": str(definition["description"]),
                "kind": "openapi",
                "version": {
                    "version": "1.0.0",
                    "config": {
                        "source": "description",
                        "base_url": "",
                        "connection": definition["connection"],
                        "allow_hosts": [host] if host else [],
                        "spec": {
                            "openapi": "3.0.3",
                            "info": {"title": definition["title"], "version": "1.0.0"},
                            "paths": {
                                "/": {
                                    str(definition["method"]).lower(): {
                                        "operationId": definition["name"],
                                        "summary": definition["title"],
                                        "description": definition["description"],
                                        "responses": {
                                            "200": {"description": definition["returns"] or "ok"}
                                        },
                                    }
                                }
                            },
                        },
                        "openapi": {"operations": [definition["name"]]},
                    },
                },
            },
        )
        self._point_at_url(created, definition)
        self._publish(actor, created)
        return self.registry.get_server(actor, uuid.UUID(str(created["id"])))

    def _document(self, body: dict[str, object]) -> dict[str, object]:
        raw = body.get("document")
        url = str(body.get("url") or "").strip()
        if raw is None and not url:
            raise ValidationFailedError("paste a document or provide a URL")
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw.strip():
            try:
                return load_document(raw)
            except OpenApiError as exc:
                raise ValidationFailedError(exc.reason) from exc
        try:
            downloaded = fetch_document(self.store, url)
            return load_document(downloaded)
        except (OpenApiError, ValueError) as exc:
            raise ValidationFailedError(str(exc)) from exc

    def _drop_spec(self, created: dict[str, object]) -> None:
        version_id = _version_id(created)
        version = self.store.tool_server_versions.get(version_id)
        if not isinstance(version, dict):
            return
        config = version.get("config")
        if isinstance(config, dict):
            config.pop("spec", None)
            nested = config.get("openapi")
            if isinstance(nested, dict):
                nested.pop("spec", None)
                nested.pop("document", None)

    def _point_at_url(self, created: dict[str, object], definition: dict[str, object]) -> None:
        """Described tools call the URL from the sentence, not a generated path."""
        version_id = _version_id(created)
        for row in self.store.tool_versions.values():
            if row.get("tool_server_version_id") != version_id:
                continue
            notes = row.get("annotations")
            bag = dict(notes) if isinstance(notes, dict) else {}
            http = bag.get("_http")
            operation = dict(http) if isinstance(http, dict) else {}
            operation["url"] = definition["url"]
            operation["method"] = definition["method"]
            operation["path"] = ""
            operation["source"] = "description"
            operation["connection"] = definition["connection"]
            bag["_http"] = operation
            row["annotations"] = bag
            row["input_schema"] = definition["input_schema"]
            row["description"] = definition["description"]
        self._drop_spec(created)

    def _publish(self, actor: Actor, created: dict[str, object]) -> None:
        server_id = uuid.UUID(str(created["id"]))
        version_id = _version_id(created)
        if version_id is None:
            return
        for row in self.store.tool_versions.values():
            if row.get("tool_server_version_id") == version_id:
                row["risk_confirmed"] = True
        try:
            self.registry.submit(actor, server_id, version_id)
        except ValidationFailedError, ArError:
            return
        if not actor.has("tools:review"):
            return
        try:
            self.registry.approve(actor, server_id, version_id, "Imported from the tools screen.")
        except ArError:
            return


def _version_id(created: dict[str, object]) -> uuid.UUID | None:
    versions = created.get("versions")
    if not isinstance(versions, list) or not versions or not isinstance(versions[0], dict):
        return None
    try:
        return uuid.UUID(str(versions[0].get("id")))
    except ValueError:
        return None
