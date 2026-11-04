# M23 checklist

Proof date: 2026-11-04. Model: Qwen/Qwen3-32B through DeepInfra. The provider key was read from `AR_CERT_LLM_API_KEY` at runtime and is not in this file.

Isolated platform Postgres was `127.0.0.1:55440`. The customer database was `127.0.0.1:55432`. The API listened on `18123`. The operator compose stack was not migrated or queried. A fresh `make up` was not pointed at that stack. Survival was a new API process against the same migrated database after the first process was stopped.

- [x] Service connection `proofapi`, data connection `walmart`, described tool server `zen` and alias `qwenm23` were listed after the API process was replaced
- [x] The new process answered `SELECT count(*) FROM public.stores` with 2992, the real table, not the demo warehouse
- [x] API JSON for the data connection has no DSN. Evidence and this checklist have no provider key
- [x] Public Walmart store-openings CSV (plotly/datasets, 2992 data rows) loaded into `public.stores`. The model reported 2992
- [x] Top state is TX with 315 stores (then FL 175, CA 159, IL 130, OH 124), matching the query result
- [x] A later turn queried `public.walmart`, got `sql_rejected` / not allowlisted, called `data.list_tables`, then counted `public.stores`
- [x] `general.chart` wrote a bar chart PNG (`Drew a bar chart (5 points)`)
- [x] `general.export_table` wrote `top_states.xlsx` from rows
- [x] Uploaded `walmart.csv` and `test1.xlsx` (pandas `test1.xlsx`, a small published workbook) were inspected, including sheet1 and sheet2
- [x] `DROP TABLE stores` through `data.query` failed with `only a single select is allowed`. The table still had 2992 rows. The analyst role has `SELECT` only
- [x] The plain-text turn was audited as `run.retried` with `{"reason": "structured_output"}`. The final answer was JSON `{"answer":"hello","rows":0}`
- [x] Playwright screenshots: connections and editor, light and dark, desktop and mobile, in this directory. Walkthrough: `walkthrough.webm`

Unit tests in `test_m23_tools.py` also reject a second statement, `COPY`, `pg_sleep`, `lo_import`, `nextval`, a write CTE, the platform database and a link-local address, and they record the read-only session commands.
