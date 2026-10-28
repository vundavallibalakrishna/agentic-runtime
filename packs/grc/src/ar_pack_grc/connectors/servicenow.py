"""ServiceNow ITSM and GRC tables. Reads are R0. Writes are W2."""

from ar_pack_grc.connectors.kit import Tool

SLUG = "grc_servicenow"
TITLE = "ServiceNow"
SYSTEMS = "ServiceNow ITSM and GRC"
TOOLS = (
    Tool("get_records", "Get records", "R0", "GET", "/api/now/table/incident"),
    Tool("create_record", "Create a record", "W2", "POST", "/api/now/table/incident"),
    Tool("update_record", "Update a record", "W2", "PATCH", "/api/now/table/incident"),
)
