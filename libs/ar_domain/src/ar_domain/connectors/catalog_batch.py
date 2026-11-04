"""Batch-two connector definitions. The shared runtime performs the calls."""

# ruff: noqa: E501, S106

from __future__ import annotations

from ar_domain.connectors.catalog import ConnectorDef, FieldDef, ToolDef, _tool

_READ = "R0"
_WRITE = "W2"
_NOT_LIVE = "not_live"
_SNOW = "https://www.servicenow.com/docs/bundle/yokohama-platform-security/page/administer/security/concept/c_OAuthAuthorizationCodeAPI.html"
_SF = "https://help.salesforce.com/s/articleView?id=sf.connected_app_create_api_integration.htm"
_ZD = "https://support.zendesk.com/hc/en-us/articles/4408889192858"
_HS = "https://developers.hubspot.com/docs/guides/apps/private-apps/overview"
_OKTA = "https://developer.okta.com/docs/guides/create-an-api-token/main/"
_ENTRA = "https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app"
_AWS = "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html"
_AZURE = (
    "https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow"
)
_GCP = "https://cloud.google.com/iam/docs/keys-create-delete"


def batch_definitions() -> list[tuple[ConnectorDef, tuple[ToolDef, ...]]]:
    return [
        _servicenow(),
        _salesforce(),
        _zendesk(),
        _hubspot(),
        _okta(),
        _entra(),
        _aws(),
        _azure(),
        _gcp(),
    ]


def _servicenow() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="servicenow",
        name="ServiceNow",
        category="Work",
        summary="Read, create and update incidents and changes, and query a table.",
        auth_kind="basic",
        auth_kinds=("basic", "oauth_authorization_code"),
        scopes=("useraccount",),
        registration_url=_SNOW,
        authorize_url="{baseUrl}/oauth_auth.do",
        token_url="{baseUrl}/oauth_token.do",
        steps=(
            "This connector uses your ServiceNow instance. The platform does not hold a ServiceNow account.",
            "Basic auth: the username is the instance user and the secret is the password. The user needs the itil role, or sn_incident_read plus sn_change_read when writes stay off.",
            "Set the site URL to https://your-instance.service-now.com.",
            "OAuth: in the instance open System OAuth, Application Registry, Create an OAuth API endpoint for external clients. The docs are at the provider page.",
            "Redirect URL is this platform's service-connection callback. The scope useraccount identifies the user.",
            "Creating or updating an incident or a change asks for approval. Skip those tools, and the itil write role, when you only want reads.",
        ),
        verification=_NOT_LIVE,
        verification_note=(
            "Not live-tested. Tools match ServiceNow Table API examples. No instance was connected."
        ),
        rate_per_minute=30,
        base_url="",
        probe_method="GET",
        probe_path="/api/now/table/incident?sysparm_limit=1",
        docs="docs/11-connectors/servicenow.md",
        fields=(FieldDef("baseUrl", "Instance URL", "https://your-instance.service-now.com"),),
        tools=(),
    )
    tools = (
        _tool(
            "get_incident",
            "Read an incident",
            "Read one incident by sys_id.",
            _READ,
            "GET",
            "/api/now/table/incident/{sys_id}",
            required=("sys_id",),
        ),
        _tool(
            "create_incident",
            "Create an incident",
            "Create an incident.",
            _WRITE,
            "POST",
            "/api/now/table/incident",
            body=("short_description", "description", "urgency", "category"),
            required=("short_description",),
        ),
        _tool(
            "update_incident",
            "Update an incident",
            "Update an incident.",
            _WRITE,
            "PATCH",
            "/api/now/table/incident/{sys_id}",
            body=("short_description", "description", "urgency", "category"),
            required=("sys_id",),
        ),
        _tool(
            "get_change",
            "Read a change",
            "Read one change request by sys_id.",
            _READ,
            "GET",
            "/api/now/table/change_request/{sys_id}",
            required=("sys_id",),
        ),
        _tool(
            "create_change",
            "Create a change",
            "Create a change request.",
            _WRITE,
            "POST",
            "/api/now/table/change_request",
            body=("short_description", "description", "category", "type"),
            required=("short_description",),
        ),
        _tool(
            "update_change",
            "Update a change",
            "Update a change request.",
            _WRITE,
            "PATCH",
            "/api/now/table/change_request/{sys_id}",
            body=("short_description", "description", "category", "type"),
            required=("sys_id",),
        ),
        _tool(
            "query_table",
            "Query a table",
            "Query a table with an encoded query.",
            _READ,
            "GET",
            "/api/now/table/{table}",
            query=("sysparm_query", "sysparm_limit", "sysparm_offset"),
            page="servicenow",
            required=("table",),
        ),
    )
    return connector, tools


def _salesforce() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="salesforce",
        name="Salesforce",
        category="Work",
        summary="Run SOQL, read a record, create and update a record, and describe an object.",
        auth_kind="oauth_authorization_code",
        auth_kinds=("oauth_authorization_code", "oauth_client_credentials", "bearer"),
        scopes=("api", "refresh_token"),
        registration_url=_SF,
        authorize_url="https://login.salesforce.com/services/oauth2/authorize",
        token_url="https://login.salesforce.com/services/oauth2/token",
        steps=(
            "In Setup, open App Manager and choose New Connected App. Enable OAuth.",
            "Callback URL is this platform's service-connection callback. Selected OAuth scopes are api and refresh_token (Perform requests at any time).",
            "Copy the consumer key into Client id and the consumer secret into the secret.",
            "Set the site URL to the instance, for example https://your-domain.my.salesforce.com. Calls do not go to login.salesforce.com.",
            "A bearer token you already hold can be pasted instead of completing OAuth. It is not shown again.",
            "Client credentials need the connected-app flow enabled for that app. Creating or updating a record asks for approval.",
        ),
        verification=_NOT_LIVE,
        verification_note=(
            "Not live-tested. Tools match Salesforce REST API v59.0 examples. No org was connected."
        ),
        rate_per_minute=30,
        base_url="",
        probe_method="GET",
        probe_path="/services/data/v59.0/limits",
        docs="docs/11-connectors/salesforce.md",
        fields=(FieldDef("baseUrl", "Instance URL", "https://your-domain.my.salesforce.com"),),
        tools=(),
    )
    tools = (
        _tool(
            "query",
            "SOQL query",
            "Run a SOQL query.",
            _READ,
            "GET",
            "/services/data/v59.0/query",
            query=("q",),
            page="next_url",
            required=("q",),
        ),
        _tool(
            "get_record",
            "Get a record",
            "Read one record by id.",
            _READ,
            "GET",
            "/services/data/v59.0/sobjects/{object}/{record_id}",
            required=("object", "record_id"),
        ),
        _tool(
            "create_record",
            "Create a record",
            "Create a record from a JSON fields object.",
            _WRITE,
            "POST",
            "/services/data/v59.0/sobjects/{object}",
            body=("fields",),
            required=("object", "fields"),
        ),
        _tool(
            "update_record",
            "Update a record",
            "Update a record from a JSON fields object.",
            _WRITE,
            "PATCH",
            "/services/data/v59.0/sobjects/{object}/{record_id}",
            body=("fields",),
            required=("object", "record_id", "fields"),
        ),
        _tool(
            "describe",
            "Describe an object",
            "Describe an sObject.",
            _READ,
            "GET",
            "/services/data/v59.0/sobjects/{object}/describe",
            required=("object",),
        ),
    )
    return connector, tools


def _zendesk() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="zendesk",
        name="Zendesk",
        category="Work",
        summary="Search tickets, read a ticket, create a ticket and add a comment.",
        auth_kind="basic",
        auth_kinds=("basic", "bearer"),
        scopes=("tickets:read", "tickets:write"),
        registration_url=_ZD,
        authorize_url="",
        token_url="",
        steps=(
            "Open Admin Center, Apps and integrations, APIs, Zendesk API. Enable token access and add a token. The guide is the provider page.",
            "Username is the agent email plus /token, for example you@company.com/token. The secret is the API token.",
            "Set the site URL to https://your-subdomain.zendesk.com.",
            "OAuth scopes, if you use a bearer token from your own Zendesk OAuth client, are tickets:read and tickets:write. Skip tickets:write when comments and new tickets stay off.",
            "Creating a ticket or adding a comment asks for approval.",
        ),
        verification=_NOT_LIVE,
        verification_note=(
            "Not live-tested. Tools match Zendesk Support API examples. No subdomain was connected."
        ),
        rate_per_minute=30,
        base_url="",
        probe_method="GET",
        probe_path="/api/v2/users/me.json",
        docs="docs/11-connectors/zendesk.md",
        fields=(FieldDef("baseUrl", "Site URL", "https://your-subdomain.zendesk.com"),),
        tools=(),
    )
    tools = (
        _tool(
            "search_tickets",
            "Search tickets",
            "Search tickets.",
            _READ,
            "GET",
            "/api/v2/search.json",
            query=("query",),
            page="next_url",
            required=("query",),
        ),
        _tool(
            "read_ticket",
            "Read a ticket",
            "Read one ticket.",
            _READ,
            "GET",
            "/api/v2/tickets/{ticket_id}.json",
            required=("ticket_id",),
        ),
        _tool(
            "create_ticket",
            "Create a ticket",
            "Create a ticket.",
            _WRITE,
            "POST",
            "/api/v2/tickets.json",
            body=("subject", "comment"),
            required=("subject", "comment"),
        ),
        _tool(
            "add_comment",
            "Add a comment",
            "Add a public comment to a ticket.",
            _WRITE,
            "PUT",
            "/api/v2/tickets/{ticket_id}.json",
            body=("comment",),
            required=("ticket_id", "comment"),
        ),
    )
    return connector, tools


def _hubspot() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="hubspot",
        name="HubSpot",
        category="Work",
        summary="Search and read contacts and companies, create and update a contact, and list deals.",
        auth_kind="bearer",
        auth_kinds=("bearer", "oauth_authorization_code"),
        scopes=(
            "crm.objects.contacts.read",
            "crm.objects.contacts.write",
            "crm.objects.companies.read",
            "crm.objects.deals.read",
        ),
        registration_url=_HS,
        authorize_url="https://app.hubspot.com/oauth/authorize",
        token_url="https://api.hubapi.com/oauth/v1/token",
        steps=(
            "In HubSpot, open Development, Legacy apps, and create a private app. The guide is the provider page.",
            "Scopes: crm.objects.contacts.read, crm.objects.contacts.write, crm.objects.companies.read and crm.objects.deals.read. Leave contacts.write off when the agent should not change contacts.",
            "Copy the access token and paste it as a bearer secret. It starts with pat-.",
            "A public OAuth app uses https://app.hubspot.com/oauth/authorize and https://api.hubapi.com/oauth/v1/token with the same scopes.",
            "Creating or updating a contact asks for approval.",
        ),
        verification=_NOT_LIVE,
        verification_note=(
            "Not live-tested. Tools match HubSpot CRM v3 examples. No portal was connected."
        ),
        rate_per_minute=30,
        base_url="https://api.hubapi.com",
        probe_method="GET",
        probe_path="/crm/v3/objects/contacts?limit=1",
        docs="docs/11-connectors/hubspot.md",
        tools=(),
    )
    tools = (
        _tool(
            "search_contacts",
            "Search contacts",
            "Search contacts.",
            _READ,
            "POST",
            "/crm/v3/objects/contacts/search",
            body=("query",),
            page="after",
        ),
        _tool(
            "read_contact",
            "Read a contact",
            "Read one contact.",
            _READ,
            "GET",
            "/crm/v3/objects/contacts/{contact_id}",
            required=("contact_id",),
        ),
        _tool(
            "search_companies",
            "Search companies",
            "Search companies.",
            _READ,
            "POST",
            "/crm/v3/objects/companies/search",
            body=("query",),
            page="after",
        ),
        _tool(
            "read_company",
            "Read a company",
            "Read one company.",
            _READ,
            "GET",
            "/crm/v3/objects/companies/{company_id}",
            required=("company_id",),
        ),
        _tool(
            "create_contact",
            "Create a contact",
            "Create a contact.",
            _WRITE,
            "POST",
            "/crm/v3/objects/contacts",
            body=("email", "firstname", "lastname"),
            required=("email",),
        ),
        _tool(
            "update_contact",
            "Update a contact",
            "Update a contact.",
            _WRITE,
            "PATCH",
            "/crm/v3/objects/contacts/{contact_id}",
            body=("email", "firstname", "lastname"),
            required=("contact_id",),
        ),
        _tool(
            "list_deals",
            "List deals",
            "List deals.",
            _READ,
            "GET",
            "/crm/v3/objects/deals",
            query=("limit", "after"),
            page="after",
        ),
    )
    return connector, tools


def _okta() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="okta",
        name="Okta",
        category="Identity",
        summary="List and read users and groups, list app assignments, and deactivate a user.",
        auth_kind="bearer",
        auth_kinds=("bearer", "oauth_authorization_code"),
        scopes=("okta.users.read", "okta.users.manage", "okta.groups.read", "okta.apps.read"),
        registration_url=_OKTA,
        authorize_url="{baseUrl}/oauth2/v1/authorize",
        token_url="{baseUrl}/oauth2/v1/token",
        steps=(
            "In the Okta admin console open Security, API, Tokens, Create token. The guide is the provider page. The token is shown once.",
            "Paste the token as a bearer secret. The connector sends it as Authorization: SSWS. Do not type the SSWS prefix yourself.",
            "Set the site URL to your org, for example https://dev-123456.okta.com.",
            "The token's admin role needs users and groups read. App assignment reads need an apps read role. Deactivate needs a user-management role. Leave that tool off when you only want reads.",
            "OAuth service-app scopes are okta.users.read, okta.groups.read, okta.apps.read and okta.users.manage. Authorize and token URLs are on your org under /oauth2/v1/.",
            "Deactivating a user asks for approval.",
        ),
        verification=_NOT_LIVE,
        verification_note=(
            "Not live-tested. Tools match Okta Users, Groups and Apps API examples. No org was connected."
        ),
        rate_per_minute=30,
        base_url="",
        probe_method="GET",
        probe_path="/api/v1/users?limit=1",
        docs="docs/11-connectors/okta.md",
        fields=(FieldDef("baseUrl", "Org URL", "https://dev-123456.okta.com"),),
        tools=(),
    )
    tools = (
        _tool(
            "list_users",
            "List users",
            "List users.",
            _READ,
            "GET",
            "/api/v1/users",
            query=("limit",),
            page="link",
        ),
        _tool(
            "read_user",
            "Read a user",
            "Read one user.",
            _READ,
            "GET",
            "/api/v1/users/{user_id}",
            required=("user_id",),
        ),
        _tool(
            "list_groups",
            "List groups",
            "List groups.",
            _READ,
            "GET",
            "/api/v1/groups",
            query=("limit",),
            page="link",
        ),
        _tool(
            "read_group",
            "Read a group",
            "Read one group.",
            _READ,
            "GET",
            "/api/v1/groups/{group_id}",
            required=("group_id",),
        ),
        _tool(
            "list_app_users",
            "List app assignments",
            "List users assigned to an app.",
            _READ,
            "GET",
            "/api/v1/apps/{app_id}/users",
            query=("limit",),
            page="link",
            required=("app_id",),
        ),
        _tool(
            "deactivate_user",
            "Deactivate a user",
            "Deactivate a user. This asks for approval.",
            _WRITE,
            "POST",
            "/api/v1/users/{user_id}/lifecycle/deactivate",
            required=("user_id",),
        ),
    )
    return connector, tools


def _entra() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="entra",
        name="Microsoft Entra ID",
        category="Identity",
        summary="List and read users and groups, and read app registrations and sign-in logs.",
        auth_kind="oauth_client_credentials",
        auth_kinds=("oauth_client_credentials", "oauth_authorization_code"),
        scopes=("https://graph.microsoft.com/.default",),
        registration_url=_ENTRA,
        authorize_url="https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        steps=(
            "Open Entra app registrations and choose New registration. The guide is the provider page. Accounts in this organizational directory only.",
            "Certificates and secrets, New client secret. Client id is the application id. The secret is the client secret value.",
            "API permissions, Microsoft Graph, application permissions: User.Read.All, Group.Read.All, Application.Read.All and AuditLog.Read.All. Grant admin consent.",
            "The token request uses scope https://graph.microsoft.com/.default. Set Tenant id to the directory id.",
            "A delegated sign-in can use the same permissions as delegated scopes plus offline_access. These tools are reads.",
            "Sign-in logs need a licence that includes them, and AuditLog.Read.All. The connector does not write directory objects.",
        ),
        verification=_NOT_LIVE,
        verification_note=(
            "Not live-tested. Tools match Microsoft Graph examples. No directory was connected."
        ),
        rate_per_minute=30,
        base_url="https://graph.microsoft.com/v1.0",
        probe_method="GET",
        probe_path="/users?$top=1",
        docs="docs/11-connectors/entra.md",
        fields=(FieldDef("tenantId", "Tenant id", "00000000-0000-0000-0000-000000000000"),),
        tools=(),
    )
    tools = (
        _tool(
            "list_users",
            "List users",
            "List users.",
            _READ,
            "GET",
            "/users",
            query=("$top",),
            page="next_url",
        ),
        _tool(
            "read_user",
            "Read a user",
            "Read one user.",
            _READ,
            "GET",
            "/users/{user_id}",
            required=("user_id",),
        ),
        _tool(
            "list_groups",
            "List groups",
            "List groups.",
            _READ,
            "GET",
            "/groups",
            query=("$top",),
            page="next_url",
        ),
        _tool(
            "read_group",
            "Read a group",
            "Read one group.",
            _READ,
            "GET",
            "/groups/{group_id}",
            required=("group_id",),
        ),
        _tool(
            "list_apps",
            "List app registrations",
            "List application registrations.",
            _READ,
            "GET",
            "/applications",
            query=("$top",),
            page="next_url",
        ),
        _tool(
            "list_signins",
            "List sign-in logs",
            "List directory sign-in logs.",
            _READ,
            "GET",
            "/auditLogs/signIns",
            query=("$top",),
            page="next_url",
        ),
    )
    return connector, tools


def _aws() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="aws",
        name="AWS",
        category="Cloud",
        summary="Read EC2 instances, S3 buckets, IAM users and policies, and CloudTrail events.",
        auth_kind="basic",
        auth_kinds=("basic",),
        scopes=("ReadOnlyAccess",),
        registration_url=_AWS,
        authorize_url="",
        token_url="",
        steps=(
            "Create an IAM user or a role in your account. Attach the AWS managed policy ReadOnlyAccess, or a tighter policy with the actions below. The guide is the provider page.",
            "The connector calls ec2:DescribeInstances, s3:ListAllMyBuckets, iam:ListUsers, iam:ListPolicies and cloudtrail:LookupEvents. It does not call a write API.",
            "Username is the access key id. Secret is the secret access key. A temporary session token, when you have one, goes on the second line of the secret.",
            "Set the region, for example us-east-1. IAM calls are signed for us-east-1, which is where that API lives.",
            "To use a role, paste its ARN in Role ARN. The access key must be allowed to call sts:AssumeRole on that role. An external id is optional.",
            "Endpoint is only for a reference server you run. Leave it empty to call AWS.",
        ),
        verification=_NOT_LIVE,
        verification_note=(
            "Not live-tested against AWS. Signature Version 4 matches Amazon's published "
            "S3 GET and PUT examples. No AWS account was called."
        ),
        rate_per_minute=20,
        base_url="",
        probe_method="POST",
        probe_path="",
        docs="docs/11-connectors/aws.md",
        fields=(
            FieldDef("region", "Region", "us-east-1"),
            FieldDef("roleArn", "Role ARN", "arn:aws:iam::123456789012:role/ReadOnly"),
            FieldDef("externalId", "External id", ""),
            FieldDef("endpoint", "Endpoint override", ""),
        ),
        tools=(),
    )
    tools = (
        _tool(
            "list_instances",
            "List EC2 instances",
            "List EC2 instances in the region.",
            _READ,
            "POST",
            "",
            kind="aws",
        ),
        _tool(
            "describe_instance",
            "Describe an EC2 instance",
            "Describe one EC2 instance.",
            _READ,
            "POST",
            "",
            required=("instance_id",),
            kind="aws",
        ),
        _tool(
            "list_buckets",
            "List S3 buckets",
            "List S3 buckets in the account.",
            _READ,
            "GET",
            "",
            kind="aws",
        ),
        _tool("list_iam_users", "List IAM users", "List IAM users.", _READ, "GET", "", kind="aws"),
        _tool(
            "list_iam_policies",
            "List IAM policies",
            "List customer-managed IAM policies.",
            _READ,
            "GET",
            "",
            kind="aws",
        ),
        _tool(
            "list_cloudtrail_events",
            "List CloudTrail events",
            "List recent CloudTrail events.",
            _READ,
            "POST",
            "",
            kind="aws",
        ),
    )
    return connector, tools


def _azure() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="azure",
        name="Azure",
        category="Cloud",
        summary="Read resources, resource groups, virtual machine state and role assignments.",
        auth_kind="oauth_client_credentials",
        auth_kinds=("oauth_client_credentials", "bearer"),
        scopes=("https://management.azure.com/.default",),
        registration_url=_AZURE,
        authorize_url="https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        steps=(
            "Register an app in Microsoft Entra. Create a client secret. The token steps are the provider page.",
            "On the subscription, assign the Reader role to the app. Role assignment reads also need Reader, or a custom role with Microsoft.Authorization/roleAssignments/read.",
            "Client id is the application id. The secret is the client secret. Set Tenant id and Subscription id.",
            "The token request is client credentials with scope https://management.azure.com/.default. The token is cached and refreshed.",
            "A bearer token you minted yourself can be pasted instead. These tools only call the Azure Resource Manager read APIs.",
        ),
        verification=_NOT_LIVE,
        verification_note=(
            "Not live-tested. The client-credentials form matches Microsoft's published example. "
            "No subscription was connected."
        ),
        rate_per_minute=30,
        base_url="https://management.azure.com",
        probe_method="GET",
        probe_path="",
        docs="docs/11-connectors/azure.md",
        fields=(
            FieldDef("tenantId", "Tenant id", "00000000-0000-0000-0000-000000000000"),
            FieldDef("subscriptionId", "Subscription id", "00000000-0000-0000-0000-000000000000"),
        ),
        tools=(),
    )
    tools = (
        _tool(
            "list_resources",
            "List resources",
            "List resources in the subscription.",
            _READ,
            "GET",
            "/subscriptions/{subscription}/resources",
            query=("api-version",),
            page="next_url",
        ),
        _tool(
            "list_resource_groups",
            "List resource groups",
            "List resource groups.",
            _READ,
            "GET",
            "/subscriptions/{subscription}/resourcegroups",
            query=("api-version",),
            page="next_url",
        ),
        _tool(
            "vm_state",
            "Read virtual machine state",
            "Read a virtual machine's instance view.",
            _READ,
            "GET",
            "/subscriptions/{subscription}/resourceGroups/{group}/providers/Microsoft.Compute/virtualMachines/{name}/instanceView",
            query=("api-version",),
            required=("group", "name"),
        ),
        _tool(
            "list_role_assignments",
            "List role assignments",
            "List role assignments on the subscription.",
            _READ,
            "GET",
            "/subscriptions/{subscription}/providers/Microsoft.Authorization/roleAssignments",
            query=("api-version",),
            page="next_url",
        ),
    )
    return connector, tools


def _gcp() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="gcp",
        name="Google Cloud",
        category="Cloud",
        summary="Read projects, compute instances, storage buckets and IAM policies.",
        auth_kind="api_key",
        auth_kinds=("api_key",),
        scopes=("https://www.googleapis.com/auth/cloud-platform.read-only",),
        registration_url=_GCP,
        authorize_url="",
        token_url="https://oauth2.googleapis.com/token",
        steps=(
            "In Google Cloud IAM, create a service account. Grant it roles/viewer, or roles/browser plus the read roles for Compute, Storage and Resource Manager. The key guide is the provider page.",
            "Create a JSON key and paste the whole file as the secret. The private key is not sent to the model.",
            "The connector builds the JWT Google documents (iss, scope, aud, iat, exp) and exchanges it at https://oauth2.googleapis.com/token. The bearer is cached and refreshed.",
            "Scope is https://www.googleapis.com/auth/cloud-platform.read-only. These tools do not create or change cloud resources.",
            "Set Project id. Zone defaults to us-central1-a for the instance list.",
        ),
        verification=_NOT_LIVE,
        verification_note=(
            "Not live-tested. The JWT matches Google's service-account example and is checked "
            "with the public key. No project was connected."
        ),
        rate_per_minute=30,
        base_url="https://cloudresourcemanager.googleapis.com",
        probe_method="GET",
        probe_path="/v1/projects?pageSize=1",
        docs="docs/11-connectors/gcp.md",
        fields=(
            FieldDef("projectId", "Project id", "my-project"),
            FieldDef("zone", "Zone", "us-central1-a"),
        ),
        tools=(),
    )
    tools = (
        _tool(
            "list_projects",
            "List projects",
            "List projects the service account can see.",
            _READ,
            "GET",
            "https://cloudresourcemanager.googleapis.com/v1/projects",
            query=("pageSize", "pageToken"),
            page="token",
        ),
        _tool(
            "list_instances",
            "List compute instances",
            "List compute instances in a zone.",
            _READ,
            "GET",
            "https://compute.googleapis.com/compute/v1/projects/{project}/zones/{zone}/instances",
            query=("pageToken",),
            page="token",
        ),
        _tool(
            "list_buckets",
            "List storage buckets",
            "List storage buckets in a project.",
            _READ,
            "GET",
            "https://storage.googleapis.com/storage/v1/b",
            query=("project", "pageToken"),
            page="token",
        ),
        _tool(
            "get_iam_policy",
            "Read an IAM policy",
            "Read a project's IAM policy.",
            _READ,
            "POST",
            "https://cloudresourcemanager.googleapis.com/v1/projects/{project}:getIamPolicy",
            required=("project",),
        ),
    )
    return connector, tools
