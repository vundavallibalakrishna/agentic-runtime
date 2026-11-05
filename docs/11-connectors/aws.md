# AWS

Read EC2 instances, S3 buckets, IAM users and policies, and CloudTrail events.

**Implementation:** Built
**Category:** Cloud
**Auth:** basic
**Verification:** Not live-tested
**Note:** Not live-tested against AWS. Signature Version 4 matches Amazon's published S3 GET and PUT examples. No AWS account was called.
**Local rate limit:** 20 calls a minute.
**Provider page:** https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html

## Setup

1. Create an IAM user or a role in your account. Attach the AWS managed policy ReadOnlyAccess, or a tighter policy with the actions below. The guide is the provider page.
2. The connector calls ec2:DescribeInstances, s3:ListAllMyBuckets, iam:ListUsers, iam:ListPolicies and cloudtrail:LookupEvents. It does not call a write API.
3. Username is the access key id. Secret is the secret access key. A temporary session token, when you have one, goes on the second line of the secret.
4. Set the region, for example us-east-1. IAM calls are signed for us-east-1, which is where that API lives.
5. To use a role, paste its ARN in Role ARN. The access key must be allowed to call sts:AssumeRole on that role. An external id is optional.
6. Endpoint is only for a reference server you run. Leave it empty to call AWS.

## Scopes

- `ReadOnlyAccess`

`ReadOnlyAccess` is an IAM policy, not an OAuth scope.

## Settings

- Region (`region`)
- Role ARN (`roleArn`)
- External id (`externalId`)
- Endpoint override (`endpoint`)

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `aws_list_instances` | List EC2 instances | R0 | List EC2 instances in the region. |
| `aws_describe_instance` | Describe an EC2 instance | R0 | Describe one EC2 instance. |
| `aws_list_buckets` | List S3 buckets | R0 | List S3 buckets in the account. |
| `aws_list_iam_users` | List IAM users | R0 | List IAM users. |
| `aws_list_iam_policies` | List IAM policies | R0 | List customer-managed IAM policies. |
| `aws_list_cloudtrail_events` | List CloudTrail events | R0 | List recent CloudTrail events. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
