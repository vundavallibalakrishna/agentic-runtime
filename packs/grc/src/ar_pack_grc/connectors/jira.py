"""Jira search, plus W2 create and update."""

from ar_pack_grc.connectors.kit import Tool

SLUG = "grc_jira"
TITLE = "Jira"
SYSTEMS = "Jira"
TOOLS = (
    Tool("search_issues", "Search issues", "R0", "GET", "/rest/api/3/search"),
    Tool("create_issue", "Create an issue", "W2", "POST", "/rest/api/3/issue"),
    Tool("update_issue", "Update an issue", "W2", "PUT", "/rest/api/3/issue"),
)
