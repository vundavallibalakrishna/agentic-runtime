# M27 connectors

## Credential scope

Batch-two secrets stay on the service connection from M23 and M26. The catalog API does not return them. Tool results do not include access keys, client secrets, session tokens or private keys.

AWS uses basic auth. The username is the access key id. The secret is the secret access key. A session token, when the customer has one, is the second line of that secret so it stays in the encrypted column. A role ARN and an external id are settings, not a second secret. The connector calls STS AssumeRole only when a role ARN is set, then caches the temporary key as sealed ciphertext on the connection.

Azure and Entra ID use the existing client-credentials connection. The token request sends `scope` when the connection has scopes: `https://management.azure.com/.default` or `https://graph.microsoft.com/.default`. Google Cloud stores a service-account JSON key as the connection secret and exchanges a JWT at `https://oauth2.googleapis.com/token`. The private key is not placed on an `Authorization` header. The connection's header name for that install is `X-AR-Service-Account`, which the Google caller replaces with the minted bearer.

Okta API tokens are sent as `Authorization: SSWS`. The stored secret is the token without that prefix.

## Least privilege

Reads are R0. Writes, including Okta deactivate, are W2, so the approval gate runs before the handler. A person can turn one tool off and skip the matching scope.

Recommended customer grants:

- ServiceNow: `itil`, or the read roles when writes are off. OAuth scope `useraccount`.
- Salesforce: `api` and `refresh_token`.
- Zendesk: `tickets:read`. Add `tickets:write` only for create and comment.
- HubSpot: contact, company and deal read scopes. Add `crm.objects.contacts.write` only for contact writes.
- Okta: `okta.users.read`, `okta.groups.read`, `okta.apps.read`. Add `okta.users.manage` only for deactivate.
- Entra ID: application permissions `User.Read.All`, `Group.Read.All`, `Application.Read.All`, `AuditLog.Read.All`. No write permission is requested.
- AWS: `ReadOnlyAccess`, or only `ec2:DescribeInstances`, `s3:ListAllMyBuckets`, `iam:ListUsers`, `iam:ListPolicies`, `cloudtrail:LookupEvents`, and `sts:AssumeRole` when a role is used. No write API is implemented.
- Azure: the Reader role on the subscription.
- Google Cloud: `https://www.googleapis.com/auth/cloud-platform.read-only`.

## Egress and signing

Connector HTTP calls use the same public-address guard as M26. Private, link-local and metadata addresses are refused. Loopback is allowed only when `AR_ENV` is `dev`, `ci` or `test`. Redirects are not followed, including a next-page URL. Each next-page URL is checked again before it is called.

AWS Signature Version 4 is computed in this repository. The secret is the HMAC key. It is not written into the query string. The unit test locks Amazon's published S3 GET Object and PUT Object signatures from the S3 developer guide (`sig-v4-header-based-auth`), including the GET signature `f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41`.

## What was tested

- Unit tests replay recorded provider examples. Those calls are not live.
- Signature Version 4 matches the two published S3 examples above. It was not checked by an AWS account.
- Azure client-credentials form matches Microsoft's published body (`grant_type`, `client_id`, `client_secret`, `scope=https://management.azure.com/.default`). The token endpoint was not called.
- Google's service-account JWT uses the documented claims (`iss`, `scope`, `aud` `https://oauth2.googleapis.com/token`, `iat`, `exp` one hour later) and the signature verifies with the public key. The token endpoint was not called.
- No ServiceNow, Salesforce, Zendesk, HubSpot, Okta, Entra ID, AWS, Azure or Google Cloud customer account was connected.
- Qwen/Qwen3-32B proof is recorded in [m27-checklist](../testing/m27-checklist.md). A replay is labelled as a replay.

## What could not be verified without credentials

- An AWS `GetCallerIdentity`, `AssumeRole` or signed read against `amazonaws.com`.
- An Azure AD token response from `login.microsoftonline.com`.
- A Google token response from `oauth2.googleapis.com`.
- Any successful read or write on the six SaaS products.

The catalog badge for each of these is Not live-tested.
