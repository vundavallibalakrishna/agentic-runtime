"""GitHub branch protection and pull-request reviews. Read only."""

from ar_pack_grc.connectors.kit import Tool

SLUG = "grc_github"
TITLE = "GitHub"
SYSTEMS = "GitHub"
TOOLS = (
    Tool("list_branch_protection", "List branch protection", "R0", "GET", "/repos/protection"),
    Tool("list_pr_reviews", "List pull request reviews", "R0", "GET", "/repos/pulls/reviews"),
)
