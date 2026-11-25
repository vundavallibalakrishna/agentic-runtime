# Document extraction (example pack)

Synthetic examples for tests and documentation. They are not customer documents and they are not a live integration.

The agent loads the schemas in the skill, calls `documents.extract`, and stops when the result lists exceptions. Those exceptions are a pending approval, reviewed on the signed review page. A person approves before anything is written onward.

`settings.targetTool` names the connector or imported API tool that receives an approved result. The pack does not call a customer system. The installer grants that tool and a policy that requires approval. Pack import does not apply policies.

## Labelled set

`labelled/sample.json` is the eval input. Scores use the `fields_match` assertion. Dates, numbers and names use the normalisers named on the case.

## Not live-tested

No customer system was called. No real model was used to produce the labelled answers. The answers are written by hand to match the synthetic text.
