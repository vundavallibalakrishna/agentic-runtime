"""Okta users, factors and admin roles. Read only."""

from ar_pack_grc.connectors.kit import Tool

SLUG = "grc_okta"
TITLE = "Okta"
SYSTEMS = "Okta"
TOOLS = (
    Tool("list_users", "List users", "R0", "GET", "/api/v1/users"),
    Tool("list_factors", "List factors", "R0", "GET", "/api/v1/factors"),
    Tool("list_admin_roles", "List admin roles", "R0", "GET", "/api/v1/roles"),
)
