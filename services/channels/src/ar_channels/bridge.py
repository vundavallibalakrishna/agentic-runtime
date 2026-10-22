"""Calls the API internal channel routes. No database import."""

from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from typing import Any


class HttpBridge:
    def __init__(self, base_url: str, token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"
        return headers

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                self.base_url + path, json=body, headers=self._headers(), timeout=5.0
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return {"action": "unavailable", "detail": "Temporarily unavailable, please retry"}
        if not response.content:
            return {}
        loaded = response.json()
        return loaded if isinstance(loaded, dict) else {}

    def get(self, path: str) -> dict[str, Any]:
        try:
            response = httpx.get(self.base_url + path, headers=self._headers(), timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError:
            return {}
        loaded = response.json()
        return loaded if isinstance(loaded, dict) else {}

    def inbound(self, message: dict[str, Any]) -> dict[str, Any]:
        return self.post("/internal/v1/channels/inbound", message)

    def approval(self, body: dict[str, Any]) -> dict[str, Any]:
        return self.post("/internal/v1/channels/approval-decisions", body)

    def integrations(self) -> list[dict[str, Any]]:
        loaded = self.get("/internal/v1/channels/integrations")
        rows = loaded.get("data") or loaded.get("items") or []
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
