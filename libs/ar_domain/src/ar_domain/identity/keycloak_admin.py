"""Keycloak admin and token calls. Spec: docs/03-specs/02-identity-tenancy.md §2."""

from typing import Protocol

import httpx


class IdpError(Exception):
    """The identity provider refused an admin call. Carries the status, never the request."""

    def __init__(self, action: str, status: int, reason: str = "") -> None:
        said = f' and said "{reason}"' if reason else ""
        super().__init__(f"identity provider refused {action} with status {status}{said}")
        self.action = action
        self.status = status
        self.reason = reason


def _reason(response: httpx.Response) -> str:
    """The provider's own words for a refusal, when it gave any. Never the request."""
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    for key in ("error_description", "errorMessage", "error"):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value[:200]
    return ""


async def admin_token(
    base_url: str, username: str, password: str, *, client: httpx.AsyncClient | None = None
) -> str:
    """Sign in to the provider's admin API and return the bearer token."""
    http = client or httpx.AsyncClient(timeout=15)
    try:
        response = await http.post(
            f"{base_url.rstrip('/')}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": username,
                "password": password,
            },
        )
    finally:
        if client is None:
            await http.aclose()
    if response.status_code != 200:
        raise IdpError("the admin sign-in", response.status_code, _reason(response))
    return str(response.json()["access_token"])


def split_issuer(issuer: str) -> tuple[str, str]:
    """``https://idp/realms/name`` to the provider base URL and the realm name."""
    base, marker, realm = issuer.rstrip("/").rpartition("/realms/")
    if not marker or not base or not realm:
        raise ValueError("the issuer must end in /realms/<name>")
    return base, realm


class KeycloakAdmin:
    """Small admin client. HTTP is injected so tests can use a mock transport."""

    def __init__(
        self, base_url: str, realm: str, token: str, client: httpx.AsyncClient | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.realm = realm
        self.token = token
        self._client = client

    async def ensure_organization(self, name: str, alias: str, domain: str) -> str:
        """Return the id of the organization with this alias, creating it when missing."""
        path = f"/admin/realms/{self.realm}/organizations"
        found = await self._send(
            "GET", path, action="the organization lookup", params={"search": alias}
        )
        for row in _rows(found):
            if row.get("alias") == alias:
                return str(row["id"])
        created = await self._send(
            "POST",
            path,
            action="the organization create",
            json={"name": name, "alias": alias, "domains": [{"name": domain, "verified": True}]},
        )
        return _created_id(created)

    async def ensure_user(self, email: str, first_name: str, last_name: str) -> str:
        """Return the id of the account with this email, creating it when missing."""
        path = f"/admin/realms/{self.realm}/users"
        found = await self._send(
            "GET", path, action="the user lookup", params={"email": email, "exact": "true"}
        )
        for row in _rows(found):
            return str(row["id"])
        created = await self._send(
            "POST",
            path,
            action="the user create",
            json={
                "username": email,
                "email": email,
                "firstName": first_name,
                "lastName": last_name,
                "enabled": True,
                "emailVerified": True,
            },
        )
        return _created_id(created)

    async def add_member(self, organization_id: str, user_id: str) -> None:
        """Put the account in the organization. Already a member is not an error."""
        await self._send(
            "POST",
            f"/admin/realms/{self.realm}/organizations/{organization_id}/members",
            action="the membership",
            json=user_id,
            accept=frozenset({409}),
        )

    async def set_password(self, user_id: str, password: str) -> None:
        """Set a permanent password. The value is sent once and never logged."""
        await self._send(
            "PUT",
            f"/admin/realms/{self.realm}/users/{user_id}/reset-password",
            action="the password change",
            json={"type": "password", "value": password, "temporary": False},
        )

    async def _send(
        self,
        method: str,
        path: str,
        *,
        action: str,
        params: dict[str, str] | None = None,
        json: object | None = None,
        accept: frozenset[int] = frozenset(),
    ) -> httpx.Response:
        client = self._client or httpx.AsyncClient(timeout=15)
        try:
            response = await client.request(
                method,
                self.base_url + path,
                headers={"Authorization": f"Bearer {self.token}"},
                params=params,
                json=json,
            )
        finally:
            if self._client is None:
                await client.aclose()
        if response.status_code >= 400 and response.status_code not in accept:
            raise IdpError(action, response.status_code, _reason(response))
        return response

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


def _rows(response: httpx.Response) -> list[dict[str, object]]:
    body = response.json() if response.content else []
    return [row for row in body if isinstance(row, dict)] if isinstance(body, list) else []


def _created_id(response: httpx.Response) -> str:
    """Keycloak answers a create with an empty body and the new id in ``Location``."""
    location = str(response.headers.get("location", ""))
    created = location.rstrip("/").rpartition("/")[2]
    if not created:
        raise IdpError("the create (no id returned)", response.status_code)
    return created


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
