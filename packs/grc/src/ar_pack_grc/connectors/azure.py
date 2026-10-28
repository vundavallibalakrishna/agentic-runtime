"""Azure Policy, Entra ID and Defender for Cloud. Read only."""

from ar_pack_grc.connectors.kit import Tool

SLUG = "grc_azure"
TITLE = "Azure"
SYSTEMS = "Azure Policy, Entra ID, Defender for Cloud"
TOOLS = (
    Tool("list_policy_states", "List policy states", "R0", "GET", "/policy/states"),
    Tool("list_users", "List users", "R0", "GET", "/users"),
    Tool("list_role_assignments", "List role assignments", "R0", "GET", "/role-assignments"),
    Tool("list_defender_alerts", "List Defender alerts", "R0", "GET", "/defender/alerts"),
)
