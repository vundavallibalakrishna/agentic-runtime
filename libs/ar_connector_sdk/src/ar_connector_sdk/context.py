"""Caller identity for a tool server. Spec: docs/05-contracts/connector-sdk.md."""

from dataclasses import dataclass


class ContextError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ToolContext:
    """Headers the gateway sends with a tool call."""

    tenant_id: str
    user_id: str
    token: str = ""
    scopes: tuple[str, ...] = ()

    @classmethod
    def from_headers(cls, headers: dict[str, str]) -> ToolContext:
        lowered = {key.lower(): value for key, value in headers.items()}
        tenant = lowered.get("x-ar-tenant-id", "")
        user = lowered.get("x-ar-user-id", "")
        if not tenant or not user:
            raise ContextError("tenant and user headers are required")
        authorization = lowered.get("authorization", "")
        token = authorization.removeprefix("Bearer ").strip() if authorization else ""
        raw_scopes = lowered.get("x-ar-scopes", "")
        scopes = tuple(part for part in raw_scopes.split(" ") if part)
        return cls(tenant_id=tenant, user_id=user, token=token, scopes=scopes)

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes:
            raise ContextError(f"missing scope {scope}")


def annotations(
    *,
    read_only: bool = False,
    destructive: bool = False,
    open_world: bool = False,
) -> dict[str, bool]:
    """MCP tool annotations a reviewer sees beside the risk class."""
    return {
        "readOnlyHint": read_only,
        "destructiveHint": destructive,
        "openWorldHint": open_world,
    }
