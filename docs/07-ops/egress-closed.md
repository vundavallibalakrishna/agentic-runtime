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

Outbound HTTP goes through `ar_common.egress_http`. `http_get` and `http_post` pass bodies, headers and query parameters to the request. The transport resolves the name off the event loop, bounded by the call timeout. A failed lookup is a refusal. The socket dials the approved address, trying the next answer when the first does not connect, while the Host header and TLS SNI stay on the original name. This holds for the sync client and the async client, including under uvloop. `proxy`, `mounts`, environment proxies and a caller-supplied `httpx` transport are rejected. `verify` and `http2` are passed through. Trust comes from `verify`, `AR_CA_BUNDLE`, `SSL_CERT_FILE` or `SSL_CERT_DIR`. SMTP, IMAP, S3 and the OTEL exporter use the same decision. S3 and OTEL keep the hostname for TLS and dial the approved address. A customer database in open mode may use a private address; link-local, metadata and the platform database stay refused, and the socket is still pinned to every address that lookup returned. The platform check compares resolved addresses with `AR_DATABASE_URL` and with `AR_PLATFORM_DB_DENY_HOSTS` and `AR_PLATFORM_DB_DENY_CIDRS`, on any port, so another database or port on that server is refused too. Closed mode passes the tenant allowlist and refuses a plaintext database: an omitted `sslmode` becomes `verify-full`, and `disable`, `allow` and `prefer` are rejected. `AR_DB_STRICT_TLS` defaults to true, so `require` is rejected as well. Set it to false only when an unverified encrypted session is acceptable. `verify-ca` and `verify-full` use `sslrootcert` when the URL sets it, otherwise `AR_CA_BUNDLE`. `sslrootcert=system` uses the default trust store. Before upgrading a closed install, set `AR_CA_BUNDLE` or put `sslrootcert=system` on each DSN. `sslcert` and `sslkey` must be absolute paths whose real path is under `AR_DB_CERT_DIR/<tenant id>/`, mode `0600` or `0640`, and unencrypted. A certificate without its key is rejected. If `AR_DB_CERT_DIR` is unset, client certificates are refused. A shared `sslrootcert` may live under `AR_DB_CERT_DIR` outside tenant folders, or it may be the `AR_CA_BUNDLE` file. Creating a connection resolves the host in the API process, so a name that does not resolve is rejected at create time. A keyword=value connection string is rejected; use a `postgresql://` or `mysql://` URL (`postgresql+psycopg` and `mysql+pymysql` are accepted and normalised). Postgres-only parameters are rejected on a MySQL URL. User, password and database are percent-decoded once. The host must be an IP literal or an RFC 1123 name. At most `AR_DB_MAX_ADDRESSES` addresses are dialled, within `AR_DB_CONNECT_DEADLINE_S`. A client created for one request does not keep that request's allowlist. Restart API and worker processes after upgrading so they load the new client and revision `0047`.

## Helm

`deploy/helm/agentic-runtime/values-airgap.yaml` sets `airgap.lockdown: true`. The chart then:

- sets `AR_EGRESS_CLOSED=true` and `AR_EGRESS_HOSTS=otel-collector`
- removes the port 443 egress rules on the shared pod policy and on mcp-gateway

Add the in-cluster model and embedding hostnames to `AR_EGRESS_HOSTS` (comma-separated) or to the tenant allowlist before saving those providers. The API and the runtime worker already have no port 443 rule. `airgap.egressPorts` is the port list opened for `airgap.egressCIDRs`. The default is 443 and 80. Add 25, 587, 993, 389 or 8000 when mail, a directory or an in-cluster model needs them.

`airgap.isolatePlatformDb` is set by the air-gap overlay. It changes egress for six pods:

| Pod | Platform database | Customer databases |
| --- | --- | --- |
| `api`, `runtime-worker`, `mcp-gateway` | Pooler, StatefulSet, or `postgres.externalCidrs` only | `airgap.tenantDbCidrs` on `airgap.tenantDbPorts` (default 5432 and 3306) |
| `sandbox-manager`, `system-worker`, `ingest-worker` | The same platform path | None. These pods keep their other in-cluster egress, except CloudNativePG instance pods |
| every other pod (`web`, `channels`, `model-gateway`, `mcp-sql`, `mcp-openapi`, `opa`, `squid`, `fake-llm`) | Denied | None from this chart |

The platform path is the CloudNativePG pooler (`cnpg.io/podRole: pooler`) in `cnpg` mode, the `app.kubernetes.io/name: postgres` pods in `statefulset` mode, or `postgres.externalCidrs` when Postgres is not bundled. CNPG instance pods (`cnpg.io/podRole: instance`) are denied for every pod while isolation is on. `postgres.externalCidrs` is also granted to the six pods when isolation is off, so an external platform database stays reachable. Isolation with an external database and an empty CIDR list fails `helm template`. A vector read DSN must use the pooler or the StatefulSet service.

`mcp-sql` in this tree does not open a database socket. Customer SQL from the product runs in `mcp-gateway` and in the API.

If `airgap.egressPorts` includes a port from `airgap.tenantDbPorts`, each `airgap.egressCIDRs` rule excludes `cluster.podCIDR`. The render fails when that port is listed and `cluster.podCIDR` is empty, because a wide CIDR would reopen the platform database pods. Ports that are not database ports are unchanged.

The chart cannot discover the cluster pod CIDR. Set `cluster.podCIDR` so the application refuses those addresses as well. The chart sets `AR_PLATFORM_DB_DENY_HOSTS` to `<release>-pg-rw`, `-ro`, `-r` and `-pooler` for CloudNativePG, and to `<release>-postgres` for the StatefulSet. A deny-list name that has never resolved is logged at startup of the next dial and reported by the API `/readyz` check `platform_db`. It does not refuse unrelated customer databases. A name that resolved before keeps its last addresses.

## Default assistant

New tenants, and a seeded assistant that has not been republished by an administrator, no longer bind `general.fetch`, `general.http` or `general.search`. Revision `0046` publishes that grant. To turn the tools back on, edit the assistant and add `fetch`, `http` and `search` to the general tool include list. Other agents are not changed.

## Re-enabling a host

Add the hostname on the Policies screen under Web access, or append it to `AR_EGRESS_HOSTS` and restart. An exact name is required for a private address.

## Data residency

`tenants.data_residency` still defaults to `in` and does not block a cloud model. Set the column to `cluster`, or set `AR_DATA_RESIDENCY=cluster` for the whole install, to require model and embedding URLs to resolve to a private or loopback address. Metadata addresses stay denied.
