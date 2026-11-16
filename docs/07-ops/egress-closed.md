# Closed egress

`AR_EGRESS_CLOSED` defaults to `false`. An existing tenant that calls a cloud model, a public connector, or web search is unchanged.

Set it to `true` to refuse outbound calls whose host is not on the tenant allowlist (`tenants.settings.egressAllowlist`) or on `AR_EGRESS_HOSTS`. The clients that consult it are:

- chat completions, including the model gateway
- embedding and rerank calls
- connector HTTP, probes, OAuth token URLs, the Google service-account exchange, AWS, SMTP, IMAP and S3 endpoints
- cloud OCR endpoints named by a tenant secret
- knowledge source fetches
- web search
- notification SMTP, web push, outbound webhook delivery, and a SIEM URL on audit export
- the OTEL exporter (skipped, not crashed, when the collector host is not listed)

`general.fetch`, `general.http` and browser navigation already require the tenant allowlist. Closed mode does not widen that.

A host named exactly on the list may resolve to a private address (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, and the IPv6 unique-local range) only when `AR_EGRESS_ALLOW_NAMED_PRIVATE` is `true`. The default is `false`. The air-gap overlay sets it to `true`. Metadata addresses, `0.0.0.0/8`, `::`, and the cloud metadata addresses `100.100.100.200`, `168.63.129.16` and `192.0.0.192` stay denied even when named, including IPv4-mapped, decimal and octal spellings. A star, a CIDR, and a wildcard of a single label (`*.com`) are not matches.

Outbound HTTP goes through `ar_common.egress_http`. `http_get` and `http_post` pass bodies, headers and query parameters to the request. The transport resolves the name off the event loop, bounded by the call timeout. A failed lookup is a refusal. The socket dials the approved address, trying the next answer when the first does not connect, while the Host header and TLS SNI stay on the original name. This holds for the sync client and the async client, including under uvloop. `proxy`, `mounts`, environment proxies and a caller-supplied `httpx` transport are rejected. `verify` and `http2` are passed through. Trust comes from `verify`, `AR_CA_BUNDLE`, `SSL_CERT_FILE` or `SSL_CERT_DIR`. SMTP, IMAP, S3 and the OTEL exporter use the same decision. S3 and OTEL keep the hostname for TLS and dial the approved address. A customer database in open mode may use a private address; link-local, metadata and the platform database stay refused, and the socket is still pinned to every address that lookup returned. The platform check compares those addresses and the port with `AR_DATABASE_URL`, so another database on the same server is refused too. Closed mode passes the tenant allowlist and refuses a plaintext database: an omitted `sslmode` becomes `verify-full`, and `disable`, `allow` and `prefer` are rejected. `verify-ca` and `verify-full` use `sslrootcert` when the URL sets it, otherwise `AR_CA_BUNDLE`. `sslrootcert=system` uses the default trust store. `sslcert` and `sslkey` must realpath under `AR_DB_CERT_DIR` (the directory of `AR_CA_BUNDLE` when that is unset). Creating a connection resolves the host in the API process, so a name that does not resolve is rejected at create time. A keyword=value connection string is rejected; use a `postgresql://` or `mysql://` URL (`postgresql+psycopg` and `mysql+pymysql` are accepted and normalised). User, password and database are percent-decoded once. A client created for one request does not keep that request's allowlist. Restart API and worker processes after upgrading so they load the new client and revision `0047`.

## Helm

`deploy/helm/agentic-runtime/values-airgap.yaml` sets `airgap.lockdown: true`. The chart then:

- sets `AR_EGRESS_CLOSED=true` and `AR_EGRESS_HOSTS=otel-collector`
- removes the port 443 egress rules on the shared pod policy and on mcp-gateway

Add the in-cluster model and embedding hostnames to `AR_EGRESS_HOSTS` (comma-separated) or to the tenant allowlist before saving those providers. The API and the runtime worker already have no port 443 rule. `airgap.egressPorts` is the port list opened for `airgap.egressCIDRs`. The default is 443 and 80. Add 25, 587, 993, 389 or 8000 when mail, a directory or an in-cluster model needs them.

## Default assistant

New tenants, and a seeded assistant that has not been republished by an administrator, no longer bind `general.fetch`, `general.http` or `general.search`. Revision `0046` publishes that grant. To turn the tools back on, edit the assistant and add `fetch`, `http` and `search` to the general tool include list. Other agents are not changed.

## Re-enabling a host

Add the hostname on the Policies screen under Web access, or append it to `AR_EGRESS_HOSTS` and restart. An exact name is required for a private address.

## Data residency

`tenants.data_residency` still defaults to `in` and does not block a cloud model. Set the column to `cluster`, or set `AR_DATA_RESIDENCY=cluster` for the whole install, to require model and embedding URLs to resolve to a private or loopback address. Metadata addresses stay denied.
