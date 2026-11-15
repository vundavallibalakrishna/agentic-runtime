# GRC pack

Optional pack for a customer-imported control catalogue, evidence links into the records vault, risks and findings. It does not ship framework prose. Statements in a catalogue are the customer's own words.

The API reads the process store, the same way the records pack does. `migrations/0001_up.sql` is the reversible Postgres schema (`grc_pack`, row-level security). `migrations/0001_down.sql` drops it. Apply the up file when a deployment wants the rows in Postgres. Core does not import this package.

Enable the pack for a tenant, then call `grc.import_catalogue`, `grc.judge_catalogue`, `grc.link_evidence`, `grc.add_risk` and `grc.add_finding`, or the routes under `/api/v1/ext/grc/`.

`grc.judge_catalogue` uses `ar_domain.documents.judgement.judge_items`. A statement that is a substring of a supplied passage is `supported`. Overlap is not a verdict.

Production loads packs from `AR_PACKS_DIR`. When signatures are required, add this pack's key id (`grc-pack`) to `AR_PACK_TRUSTED_KEYS` before the directory is loaded.
