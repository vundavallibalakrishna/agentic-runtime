# Connector dispatch matrix

Every connector installed with stub credentials; every HTTP call caught by an httpx `MockTransport` returning a generic 200. Proves each connector tool dispatches a well-formed request and parses the reply once an account is connected.

## Summary

- Total connector tools: **92**
- dispatched: **6**
- needs-oauth: **25**
- needs-egress: **55**
- needs-param: **6**
- install-failed: **0**
- failing: **0**

## email

| tool | state | note |
|---|---|---|
| `email_send` | needs-param | validation_failed: Set the SMTP host on the connector. |
| `email_list` | needs-param | validation_failed: Set the IMAP host on the connector. |
| `email_read` | needs-param | validation_failed: Set the IMAP host on the connector. |

## slack

| tool | state | note |
|---|---|---|
| `slack_list_channels` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `slack_read_channel` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `slack_post_message` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `slack_search` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |

## teams

| tool | state | note |
|---|---|---|
| `teams_list_channels` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `teams_post_message` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |

## gcal

| tool | state | note |
|---|---|---|
| `gcal_list_events` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `gcal_find_free` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `gcal_create_event` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |

## m365-calendar

| tool | state | note |
|---|---|---|
| `m365cal_list_events` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `m365cal_find_free` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `m365cal_create_event` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |

## gdrive

| tool | state | note |
|---|---|---|
| `gdrive_search` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `gdrive_list` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `gdrive_download` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `gdrive_upload` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |

## sharepoint

| tool | state | note |
|---|---|---|
| `sharepoint_search` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `sharepoint_list` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `sharepoint_download` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `sharepoint_upload` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |

## s3

| tool | state | note |
|---|---|---|
| `s3_list` | needs-param | validation_failed: Set the bucket on the connector. |
| `s3_get` | needs-param | validation_failed: Set the bucket on the connector. |
| `s3_put` | needs-param | validation_failed: Set the bucket on the connector. |

## jira

| tool | state | note |
|---|---|---|
| `jira_search` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `jira_create_issue` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `jira_update_issue` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `jira_add_comment` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |

## github

| tool | state | note |
|---|---|---|
| `github_list_repos` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `github_list_issues` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `github_list_pulls` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `github_read_file` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `github_create_issue` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `github_comment` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |

## confluence

| tool | state | note |
|---|---|---|
| `confluence_search` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `confluence_read_page` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `confluence_write_page` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |

## notion

| tool | state | note |
|---|---|---|
| `notion_search` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `notion_read_page` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `notion_read_database` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `notion_create_page` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |

## servicenow

| tool | state | note |
|---|---|---|
| `servicenow_get_incident` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `servicenow_create_incident` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `servicenow_update_incident` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `servicenow_get_change` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `servicenow_create_change` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `servicenow_update_change` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `servicenow_query_table` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |

## salesforce

| tool | state | note |
|---|---|---|
| `salesforce_query` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `salesforce_get_record` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `salesforce_create_record` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `salesforce_update_record` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |
| `salesforce_describe` | needs-oauth | credential_required: this connection has no access token yet. Reconnect the account on the connector page. |

## zendesk

| tool | state | note |
|---|---|---|
| `zendesk_search_tickets` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `zendesk_read_ticket` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `zendesk_create_ticket` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `zendesk_add_comment` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |

## hubspot

| tool | state | note |
|---|---|---|
| `hubspot_search_contacts` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `hubspot_read_contact` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `hubspot_search_companies` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `hubspot_read_company` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `hubspot_create_contact` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `hubspot_update_contact` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `hubspot_list_deals` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |

## okta

| tool | state | note |
|---|---|---|
| `okta_list_users` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `okta_read_user` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `okta_list_groups` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `okta_read_group` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `okta_list_app_users` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `okta_deactivate_user` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |

## entra

| tool | state | note |
|---|---|---|
| `entra_list_users` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `entra_read_user` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `entra_list_groups` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `entra_read_group` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `entra_list_apps` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `entra_list_signins` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |

## aws

| tool | state | note |
|---|---|---|
| `aws_list_instances` | dispatched | dispatched and parsed a reply |
| `aws_describe_instance` | dispatched | dispatched and parsed a reply |
| `aws_list_buckets` | dispatched | dispatched and parsed a reply |
| `aws_list_iam_users` | dispatched | dispatched and parsed a reply |
| `aws_list_iam_policies` | dispatched | dispatched and parsed a reply |
| `aws_list_cloudtrail_events` | dispatched | dispatched and parsed a reply |

## azure

| tool | state | note |
|---|---|---|
| `azure_list_resources` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `azure_list_resource_groups` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `azure_vm_state` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |
| `azure_list_role_assignments` | needs-egress | egress_denied: stub.example.com is blocked by the egress deny list |

## gcp

| tool | state | note |
|---|---|---|
| `gcp_list_projects` | needs-oauth | credential_required: The secret must be a Google service-account JSON key. |
| `gcp_list_instances` | needs-oauth | credential_required: The secret must be a Google service-account JSON key. |
| `gcp_list_buckets` | needs-oauth | credential_required: The secret must be a Google service-account JSON key. |
| `gcp_get_iam_policy` | needs-oauth | credential_required: The secret must be a Google service-account JSON key. |
