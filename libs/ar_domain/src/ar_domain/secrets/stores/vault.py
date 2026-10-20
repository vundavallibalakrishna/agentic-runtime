"""OpenBao KV v2 backend. Spec: docs/03-specs/03-secrets-credentials.md §2."""

import asyncio
from typing import Protocol, cast

from ar_common.errors import NotFoundError


class KvClient(Protocol):
    """Subset of hvac's KV v2 API used by the vault backend."""

    def create_or_update_secret(
        self, *, path: str, secret: dict[str, str], mount_point: str
    ) -> object:
        """Write a secret."""

    def read_secret_version(self, *, path: str, mount_point: str) -> dict[str, object]:
        """Read the latest version."""

    def delete_metadata_and_all_versions(self, *, path: str, mount_point: str) -> object:
        """Destroy every version."""


class VaultSecretStore:
    """KV v2 at ``tenants/{tenant}/secrets/{id}``. Values are bytes stored as latin-1."""

    def __init__(self, client: KvClient, *, mount: str) -> None:
        self.client = client
        self.mount = mount

    async def put(self, path: str, value: bytes, *, aad: bytes) -> None:
        del aad
        await asyncio.to_thread(
            self.client.create_or_update_secret,
            path=path,
            secret={"value": value.decode("latin-1")},
            mount_point=self.mount,
        )

    async def get(self, path: str, *, aad: bytes) -> bytes:
        del aad
        try:
            payload = await asyncio.to_thread(
                self.client.read_secret_version, path=path, mount_point=self.mount
            )
        except Exception as exc:
            raise NotFoundError("secret value not found") from exc
        data = payload.get("data")
        if not isinstance(data, dict):
            raise NotFoundError("secret value not found")
        inner = data.get("data", data)
        if not isinstance(inner, dict) or "value" not in inner:
            raise NotFoundError("secret value not found")
        return str(inner["value"]).encode("latin-1")

    async def delete(self, path: str) -> None:
        await asyncio.to_thread(
            self.client.delete_metadata_and_all_versions, path=path, mount_point=self.mount
        )


def hvac_kv(addr: str, token: str) -> KvClient:
    """Build an hvac KV v2 client. Imported lazily so tests can fake the client."""
    import hvac  # noqa: PLC0415

    client = hvac.Client(url=addr, token=token)
    return cast("KvClient", client.secrets.kv.v2)
