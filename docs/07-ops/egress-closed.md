# Closed egress

`AR_EGRESS_CLOSED` defaults to `false`. An existing tenant that calls a cloud model, a public connector, or web search is unchanged.

Set it to `true` to refuse outbound calls whose host is not on the tenant allowlist (`tenants.settings.egressAllowlist`) or on `AR_EGRESS_HOSTS`. The clients that consult it are:

- chat completions, including the model gateway
- embedding and rerank calls
- connector HTTP, AWS, SMTP, IMAP and S3 endpoints
- knowledge source fetches
- web search
- notification SMTP, web push, and a SIEM URL on audit export
- the OTEL exporter (skipped, not crashed, when the collector host is not listed)

`general.fetch`, `general.http` and browser navigation already require the tenant allowlist. Closed mode does not widen that.

A host named exactly on the list may resolve to a private address (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, and the IPv6 equivalents). That is how an on-prem mail host or object store is reached. The metadata range `169.254.0.0/16` stays denied even if it is named. A star, a CIDR, and a wildcard of a single label (`*.com`) are not matches. A wildcard such as `*.corp.example` matches a public name and does not unlock a private address.

## Helm

`deploy/helm/agentic-runtime/values-airgap.yaml` sets `airgap.lockdown: true`. The chart then:

- sets `AR_EGRESS_CLOSED=true` and `AR_EGRESS_HOSTS=otel-collector`
- removes the port 443 egress rules on the shared pod policy and on mcp-gateway

Add the in-cluster model and embedding hostnames to `AR_EGRESS_HOSTS` (comma-separated) or to the tenant allowlist before saving those providers. The API and the runtime worker already have no port 443 rule.

## Re-enabling a host

Add the hostname on the Policies screen under Web access, or append it to `AR_EGRESS_HOSTS` and restart. An exact name is required for a private address.

## Data residency

`tenants.data_residency` still defaults to `in` and does not block a cloud model. Set the column to `cluster`, or set `AR_DATA_RESIDENCY=cluster` for the whole install, to require model and embedding URLs to resolve to a private or loopback address. Metadata addresses stay denied.
