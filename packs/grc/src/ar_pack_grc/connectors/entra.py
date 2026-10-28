"""Microsoft Entra ID users, authentication methods and directory roles. Read only."""

from ar_pack_grc.connectors.kit import Tool

SLUG = "grc_entra"
TITLE = "Entra ID"
SYSTEMS = "Microsoft Entra ID"
TOOLS = (
    Tool("list_users", "List users", "R0", "GET", "/users"),
    Tool(
        "list_auth_methods", "List authentication methods", "R0", "GET", "/authentication/methods"
    ),
    Tool("list_directory_roles", "List directory roles", "R0", "GET", "/directoryRoles"),
)
