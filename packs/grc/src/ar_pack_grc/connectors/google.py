"""Google Workspace users, MFA and admin roles. Read only."""

from ar_pack_grc.connectors.kit import Tool

SLUG = "grc_google"
TITLE = "Google Workspace"
SYSTEMS = "Google Workspace"
TOOLS = (
    Tool("list_users", "List users", "R0", "GET", "/admin/directory/v1/users"),
    Tool("list_mfa", "List MFA enrolment", "R0", "GET", "/admin/directory/v1/mfa"),
    Tool("list_admin_roles", "List admin roles", "R0", "GET", "/admin/directory/v1/roles"),
)
