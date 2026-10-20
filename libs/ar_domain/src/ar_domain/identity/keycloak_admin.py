"""Keycloak admin and token calls. Spec: docs/03-specs/02-identity-tenancy.md §2."""

from typing import Protocol, cast

import httpx


class KeycloakAdmin:
    """Small admin client. HTTP is injected so tests can use a mock transport."""

    def __init__(
        self, base_url: str, realm: str, token: str, client: httpx.AsyncClient | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.realm = realm
        self.token = token
        self._client = client

    async def create_organization(self, name: str, alias: str, domain: str) -> str:
        payload = cast(
            "dict[str, object]",
            {"name": name, "alias": alias, "domains": [{"name": domain, "verified": False}]},
        )
        body = await self._post(f"/admin/realms/{self.realm}/organizations", payload)
        if isinstance(body, dict) and "id" in body:
            return str(body["id"])
        return alias

    async def create_user(self, email: str, organization_id: str) -> str:
        created = await self._post(
            f"/admin/realms/{self.realm}/users",
            {"email": email, "username": email, "enabled": True, "emailVerified": False},
        )
        user_id = str(created["id"]) if isinstance(created, dict) and "id" in created else email
        await self._post(
            f"/admin/realms/{self.realm}/organizations/{organization_id}/members",
            {"id": user_id},
        )
        return user_id

    async def set_user_enabled(self, user_id: str, *, enabled: bool) -> None:
        await self._request(
            "PUT",
            f"/admin/realms/{self.realm}/users/{user_id}",
            {"enabled": enabled},
        )

    async def delete_organization(self, organization_id: str) -> None:
        await self._request(
            "DELETE", f"/admin/realms/{self.realm}/organizations/{organization_id}", None
        )

    async def upsert_identity_provider(self, alias: str, payload: dict[str, object]) -> None:
        await self._request(
            "POST",
            f"/admin/realms/{self.realm}/identity-provider/instances",
            payload | {"alias": alias},
        )

    async def delete_identity_provider(self, alias: str) -> None:
        await self._request(
            "DELETE", f"/admin/realms/{self.realm}/identity-provider/instances/{alias}", None
        )

    async def _post(self, path: str, payload: dict[str, object]) -> object:
        return await self._request("POST", path, payload)

    async def _request(self, method: str, path: str, payload: dict[str, object] | None) -> object:
        headers = {"Authorization": f"Bearer {self.token}"}
        client = self._client or httpx.AsyncClient()
        owned = self._client is None
        try:
            response = await client.request(
                method, self.base_url + path, headers=headers, json=payload
            )
        finally:
            if owned:
                await client.aclose()
        if response.status_code >= 400:
            return {"error": response.text, "status": response.status_code}
        if response.content:
            return response.json()
        return {}


class TokenClient(Protocol):
    async def password_grant(self, username: str, password: str) -> dict[str, object]:
        """Direct grant used by tests and local login."""


async def password_grant(
    *,
    issuer: str,
    client_id: str,
    client_secret: str,
    username: str,
    password: str,
    http: httpx.AsyncClient,
) -> dict[str, object]:
    """Resource-owner password grant against the realm token endpoint."""
    response = await http.post(
        f"{issuer.rstrip('/')}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": password,
            "scope": "openid profile email organization",
        },
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        return {}
    return {str(key): value for key, value in body.items()}
