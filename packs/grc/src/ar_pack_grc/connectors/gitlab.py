"""GitLab protected branches and approvals. Read only."""

from ar_pack_grc.connectors.kit import Tool

SLUG = "grc_gitlab"
TITLE = "GitLab"
SYSTEMS = "GitLab"
TOOLS = (
    Tool(
        "list_protected_branches",
        "List protected branches",
        "R0",
        "GET",
        "/projects/protected_branches",
    ),
    Tool("list_approvals", "List merge request approvals", "R0", "GET", "/projects/approvals"),
)
