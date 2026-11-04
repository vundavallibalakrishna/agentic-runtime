# M26 connectors

## Token storage

A connector install stores the connection name and non-secret settings. The secret stays on the service connection, encrypted with AES-256-GCM under the connection key (`ar-connection-v1:` plus `AR_CURSOR_SECRET`).

OAuth access tokens and refresh tokens on credential grants are ciphertext columns added in revision 0028. `secret_ref_id` is nullable so a grant can be stored without a second secret row. The plaintext is restored only inside the process that is about to call the provider.

OAuth `state` rows store the PKCE verifier as ciphertext. Named secrets store ciphertext. None of these values are returned by the catalog API, written into tool results, or copied into the audit detail.

## Scopes and least privilege

Each connector page lists the scopes the tools need and links to the provider's app-registration page. Read tools are R0. Write tools are W2, so the existing approval gate runs before the handler. A person can turn a single tool off on the install. The setup text says which scope to skip when that write is not wanted. Examples: Drive upload needs `drive.file` and is separate from `drive.readonly`. SharePoint upload needs `Files.ReadWrite` and is separate from `Files.Read`. GitHub's documented default scope is `public_repo`, not `repo`.

## Egress

Connector HTTP calls use the same public-address guard as other outbound tools. Private, link-local and metadata addresses are refused. Loopback is allowed only when `AR_ENV` is `dev`, `ci` or `test`, so a local SMTP stand-in or MinIO can be used in development. Redirects are not followed. SMTP and S3 endpoints are checked with the same deny list before a socket is opened.

Tool results are untrusted and pass through `wrap_tool_result` on the way back to the model.

## What was tested

- Unit tests call recorded provider examples through an HTTP stand-in. Those calls are not live.
- Email send was proven against Mailpit on a local port. That is not a customer mailbox.
- S3 put and get were proven against SeaweedFS. The MinIO image could not be pulled. It is not AWS.
- GitHub read was proven against `api.github.com` for `octocat/Hello-World`. An issue was created with a token available to the proof run, not a customer account.
- Slack, Teams, both calendars, Drive, SharePoint, Jira, Confluence and Notion were not called on a live account.
- Qwen/Qwen3-32B called `github_read_file` and quoted the README heading.

The calls are recorded in [m26-checklist](../testing/m26-checklist.md).
