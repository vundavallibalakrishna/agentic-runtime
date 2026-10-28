"""AWS Config, IAM, CloudTrail and Security Hub. Read only."""

from ar_pack_grc.connectors.kit import Tool

SLUG = "grc_aws"
TITLE = "AWS"
SYSTEMS = "AWS Config, IAM, CloudTrail, Security Hub"
TOOLS = (
    Tool("list_config_rules", "List Config rules", "R0", "GET", "/config/rules"),
    Tool("list_iam_users", "List IAM users", "R0", "GET", "/iam/users"),
    Tool("get_trail_status", "Get CloudTrail status", "R0", "GET", "/cloudtrail/status"),
    Tool(
        "list_security_hub_findings",
        "List Security Hub findings",
        "R0",
        "GET",
        "/securityhub/findings",
    ),
)
