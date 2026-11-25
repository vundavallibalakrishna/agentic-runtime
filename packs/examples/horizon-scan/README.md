# Horizon scan (example pack)

A content pack that reuses the same tools as policy watch: discover, fetch, diff, routines, and delivery only when there is something to report. Sources, categories, relevance criteria and review frequency are a settings document checked against a JSON Schema. Edit them through `PUT /api/v1/resource-settings/agent/horizon-scan`. Each save is a new version and an audit row.

The agent writes candidate rows with `extensions.put`. It does not copy an external register into platform tables. A suggested link is an id returned by a connector or imported API named in settings. Writing to that system is a tool the installer grants and gates with approval for the group named in settings. The decision is the review page and the channel cards.

Digests use a routine with `something_to_report`, email, Teams or a webhook.

## Not live-tested

No licensed feed was called. The LexisNexis catalogue row is not live-tested. No customer register was written.
