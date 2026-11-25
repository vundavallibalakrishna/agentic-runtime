# Scenario runs (example pack)

The platform does not produce figures of its own. This pack stores versioned scenario records, registers a script by its hash, runs that script at a fixed entry point, and records hashes of the script, the parameters and the outputs.

Comparisons use `extensions.compare`, which computes deltas in code.

Approvals, decided on the review page and the channel cards:

- scenario agreed, as a multi-level review
- results approved, four-eyes, and the preparer is not an approver
- report issued, on `documents.create`

`examples/model.py` is a synthetic script for tests. It prints a fixed JSON object. It is not a model of any portfolio.

## LibreOffice

Headless recalculation of a workbook is not supported yet. The sandbox image includes LibreOffice, and this pack does not call it. The supported entry point is `python model.py --params params.json`, from `AR_REGISTERED_SCRIPT_ENTRY`.

## Not live-tested

No actuarial model was run. The reproducibility test uses the synthetic script only.
