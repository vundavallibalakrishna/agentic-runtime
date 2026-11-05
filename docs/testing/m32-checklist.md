# M32 checklist

Document analysis keeps the evidence a GRC check needs, and Check judges a paraphrase.

## Setting

`features.documentAnalysisRedaction` defaults to **false**. Check, compare, summarise, rewrite, gaps, extract, and the library read tools keep dates, locations, retention periods and control ids. `features.piiRedaction` (default true) still masks other tool results. The redact endpoint and outbound previews stay masked.

A root `piiRedaction` patch is stored on `features.piiRedaction`. An unknown settings key is HTTP 422. Agent `safety.piiMasking` true opts that agent back into the full mask on document tools. See [OQ-69](../open-questions.md).

## What the automated tests cover

`libs/ar_domain/tests/unit/test_m32_analysis.py`

- A passage with `90 days`, `Ireland` and `P6.3` is still in the model input when analysis mode is on, including when the recogniser would label those spans.
- The same strings are masked on the outbound profile and when `documentAnalysisRedaction` is true.
- A paraphrased MFA control is `not_found` with no model (the old overlap floor) and `met` with a quote of the login-challenge sentence when a model answers. The picnic sentence is not the citation.
- An unsupported Mars-colony control is `not_found` with no citation.
- A document read through the tool pipeline keeps the three strings.
- Ireland and Cayman both survive the compare tool text.
- `PATCH /api/v1/tenant` accepts the setting and returns 422 for an unknown key (`services/api/tests/unit/test_m32_settings.py`).

## Live proof

Model: `Qwen/Qwen3-32B` via DeepInfra when `AR_CERT_LLM_API_KEY` is set. The key is not written here.

Command: `uv run python scripts/m32_proof.py`

Result: **PASS** on 2026-11-05.

`uv run python scripts/m32_proof.py` with `AR_CERT_LLM_API_KEY` set:

- Analysis profile left `Records stay in Ireland for 90 days under control P6.3.` unchanged.
- Outbound profile produced `Records stay in [LOCATION] for [DATE_TIME] under control [US_DRIVER_LICENSE].3.`
- Check of the ACME-like policy returned `met` for the paraphrased MFA control. The quote was `Every employee completes a second login challenge before opening the production console.` The picnic sentence was not cited.
- The Mars-colony control returned `not_found` with no citation.
- Compare of the Ireland DPA and the Cayman DPA kept both names. The analysis view contained zero `[LOCATION]` tokens.
