"""Security Command Center and IAM. Read only."""

from ar_pack_grc.connectors.kit import Tool

SLUG = "grc_gcp"
TITLE = "Google Cloud"
SYSTEMS = "Security Command Center, IAM"
TOOLS = (
    Tool("list_findings", "List Security Command Center findings", "R0", "GET", "/scc/findings"),
    Tool("list_iam_policy", "List IAM policy", "R0", "GET", "/iam/policy"),
)
