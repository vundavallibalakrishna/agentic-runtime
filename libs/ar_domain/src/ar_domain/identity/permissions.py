"""Permission catalogue and system roles.

Spec: docs/06-security/authn-authz.md §3 and §4. Keys match the document exactly.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Permission:
    key: str
    category: str
    description: str


PERMISSIONS: tuple[Permission, ...] = (
    Permission("tenant:read", "tenant", "Read tenant profile and settings"),
    Permission(
        "tenant:manage",
        "tenant",
        "Update settings, domains, IdPs, SCIM tokens, support-access grants, run-callback secret",
    ),
    Permission("users:read", "identity", "List users, groups, teams, roles, assignments"),
    Permission(
        "users:manage",
        "identity",
        "Invite, suspend, edit attributes, erase users; manage local groups",
    ),
    Permission(
        "teams:manage",
        "identity",
        "Create/update/delete teams and memberships (team leads manage their own team without it)",
    ),
    Permission("roles:manage", "identity", "Custom roles and role assignments"),
    Permission("service_accounts:manage", "identity", "Service accounts and their API keys"),
    Permission("api_keys:manage_own", "identity", "Personal API keys"),
    Permission(
        "secrets:use", "secrets", "List secret names in pickers and reference them in definitions"
    ),
    Permission(
        "secrets:manage", "secrets", "Create, rotate, delete tenant secrets; credential providers"
    ),
    Permission("connections:manage_own", "secrets", "Connect/disconnect own OAuth accounts"),
    Permission("models:read", "models", "View providers, models, aliases"),
    Permission("models:manage", "models", "Manage tenant providers, models, aliases"),
    Permission(
        "chat:use",
        "chat",
        "Chat with visible agents, upload files, manage own conversations and memory",
    ),
    Permission(
        "conversations:read_all",
        "chat",
        "Read any conversation in the tenant (investigations; audited)",
    ),
    Permission("agents:read", "agents", "Browse the agent catalogue"),
    Permission("agents:create", "agents", "Create agents (become owner)"),
    Permission(
        "agents:edit", "agents", "Edit drafts of agents owned by the scope (team-scoped typical)"
    ),
    Permission(
        "agents:publish", "agents", "Publish/rollback agents they can edit; tenant visibility"
    ),
    Permission("agents:disable", "agents", "Kill switch on any agent"),
    Permission(
        "agents:manage_all",
        "agents",
        "Full control of all agents; second-person publish for high-risk agents",
    ),
    Permission("memory:manage_agent", "memory", "Review and edit agent- and team-scope memory"),
    Permission("tools:read", "tools", "Browse tool servers and tools"),
    Permission(
        "tools:create", "tools", "Register tool servers and data connections (become owner)"
    ),
    Permission("tools:review", "tools", "Approve/reject tool server versions, set risk classes"),
    Permission("tools:disable", "tools", "Kill switch on tools and servers"),
    Permission(
        "knowledge:read", "knowledge", "Browse collections visible to the user and search them"
    ),
    Permission(
        "knowledge:manage",
        "knowledge",
        "Create collections and sources; manage documents and access",
    ),
    Permission("skills:read", "skills", "Browse skills"),
    Permission("skills:create", "skills", "Create skills (become owner)"),
    Permission("skills:manage_all", "skills", "Manage all skills"),
    Permission("policies:read", "policy", "Read policies and simulate"),
    Permission("policies:manage", "policy", "Create, version, activate, disable policies"),
    Permission(
        "approvals:decide",
        "approvals",
        "Decide approvals assigned to them (by policy approver rule)",
    ),
    Permission("approvals:read_all", "approvals", "See all approvals in the tenant"),
    Permission("approvals:grant_standing", "approvals", "Create and revoke standing approvals"),
    Permission("routines:create", "routines", "Create routines (run as themselves)"),
    Permission("routines:manage_all", "routines", "Manage and transfer any routine"),
    Permission("sandboxes:manage", "sandboxes", "Manage sandbox templates; terminate any sandbox"),
    Permission("channels:manage", "channels", "Channel integrations and identities"),
    Permission("webhooks:manage", "events", "Outbound webhooks"),
    Permission("usage:read", "usage", "Usage, cost and observability overview"),
    Permission("quotas:manage", "usage", "Quotas"),
    Permission("audit:read", "audit", "Audit search and chain verification"),
    Permission("audit:export", "audit", "Audit exports"),
    Permission("evals:run", "evals", "Run eval suites"),
    Permission("evals:manage", "evals", "Manage eval suites/cases; read feedback"),
    Permission("packs:manage", "agents", "Install, upgrade and uninstall content packs"),
    Permission("reviews:read", "reviews", "Read review queues and items"),
    Permission("reviews:decide", "reviews", "Sign or reject a review item"),
    Permission("reviews:manage", "reviews", "Create and edit review queues"),
    Permission("sod:manage", "policy", "Manage segregation-of-duties constraints"),
)

PERMISSION_KEYS: frozenset[str] = frozenset(item.key for item in PERMISSIONS)

_MEMBER = (
    "tenant:read",
    "chat:use",
    "agents:read",
    "tools:read",
    "knowledge:read",
    "skills:read",
    "connections:manage_own",
    "api_keys:manage_own",
    "routines:create",
    "secrets:use",
    "models:read",
    "policies:read",
)


def _plus(*extra: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*_MEMBER, *extra)))


SYSTEM_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "member": _MEMBER,
    "builder": _plus(
        "agents:create",
        "agents:edit",
        "agents:publish",
        "skills:create",
        "evals:run",
        "evals:manage",
        "memory:manage_agent",
        "usage:read",
    ),
    "tool_owner": _plus("tools:create"),
    "knowledge_manager": _plus("knowledge:manage"),
    "approver": _plus(
        "approvals:decide",
        "approvals:grant_standing",
        "reviews:read",
        "reviews:decide",
    ),
    "auditor": _plus(
        "audit:read",
        "audit:export",
        "approvals:read_all",
        "usage:read",
        "users:read",
        "reviews:read",
    ),
    "tenant_admin": tuple(item.key for item in PERMISSIONS),
}

SYSTEM_ROLE_NAMES: dict[str, str] = {
    "member": "Member",
    "builder": "Builder",
    "tool_owner": "Tool owner",
    "knowledge_manager": "Knowledge manager",
    "approver": "Approver",
    "auditor": "Auditor",
    "tenant_admin": "Tenant admin",
}
