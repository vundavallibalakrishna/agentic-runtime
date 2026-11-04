# M23 database tool and durable secrets

## What is stored

Service connections and customer database DSNs are rows in Postgres (revision `0025`). Ciphertext is AES-256-GCM. The key is SHA-256 of the string `ar-connection-v1:` followed by `AR_CURSOR_SECRET`. Rotating `AR_CURSOR_SECRET` makes existing ciphertext unreadable until the connection is saved again. There is no automatic rewrap.

`secret_refs` for a data connection records that a DSN exists. The DSN itself is `data_connections.dsn_ciphertext`, not the secret-ref path. API views return `dsn_secret_id` and never the DSN, the password or the ciphertext.

Model provider keys use the separate envelope in `AR_DB_ENCRYPTION_KEYS`. They are loaded into the process only to call the provider. They are not logged, returned or written by the proof.

## Read-only guarantees

`data.query` accepts one `SELECT` or `UNION` after sqlglot parsing.

Rejected before a driver round-trip:

- `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, `COPY`, `MERGE`, `GRANT`
- more than one statement, including a statement hidden after a comment
- data-modifying CTEs
- `pg_sleep`, `dblink*`, `lo_*`, `nextval`, `setval`, `set_config`, `pg_read_file`, `pg_terminate_backend`
- tables outside the connection allowlist and the agent override
- `pg_catalog`, `information_schema` and `pg_*` unless the tool itself is listing the catalogue
- the platform database (same host, port and database name as `AR_DATABASE_URL`, with localhost and `127.0.0.1` treated as the same host) unless `allowlist.allowPlatform` is true
- link-local `169.254.0.0/16` and metadata host names
- DSN query parameters `options` and `init_command`

The session then sets `default_transaction_read_only`, a statement timeout, and `SET TRANSACTION READ ONLY`, and rolls back. A customer role with `SELECT` only is the second layer. MySQL uses `START TRANSACTION READ ONLY`.

Result text is wrapped as untrusted tool output. Errors have the DSN password removed.

## What was tested

Unit tests reject `DROP`, a second statement, `COPY`, `pg_sleep`, `lo_import`, `nextval`, a write CTE and `information_schema` when the caller is not the catalogue tool. They record the read-only session commands, strip `options` from a DSN, refuse the platform database and a link-local address, and check that a sealed DSN does not contain the password.

The live proof, recorded in [m23-checklist](../testing/m23-checklist.md), uses a non-superuser role and a `DROP` that the guard rejects as not a single select.

## Still process-local

Files and blobs, tool-call rows, OAuth grants, named secrets, builder sessions, policies, approvals and sandboxes stay on the process store (OQ-59).
