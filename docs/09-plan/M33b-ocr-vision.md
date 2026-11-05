# M33b — OCR canary and image questions

Depends on M32. A scanned page is readable with local OCR, and an agent can ask a question about a screenshot. Cloud OCR providers stay unwired. A vision model that is not configured fails closed.

This milestone is one pull request. It does not change seed policy, the eval harness, or Office document creation.

## M33b-T01 OCR canary and image.ask

**Spec:** [24-documents](../03-specs/24-documents.md), [m24-documents](../06-security/m24-documents.md).

**Do:**

- `documents.ocr` reads a scanned PDF or an image with tesseract, stores the extraction, and returns the text.
- The canary fixture is `docs/testing/fixtures/m33b/ocr-canary.png` and the scanned PDF next to it. The golden strings are in `ocr-canary.expected.txt`.
- Google Document AI, Amazon Textract and Azure Document Intelligence return `not_live` with the operator path for local tesseract.
- `image.ask` on `builtin://image` answers a question about a PNG, JPEG, GIF or WebP. It uses the vision alias and the same sealed provider key as chat. A fake alias or a text-only model returns `vision_unavailable`.
- The default assistant includes the image server. An assistant published earlier that already includes documents receives the same grant in memory.

**Done when:** the canary strings survive OCR when tesseract is installed, the tool says `ocr_unavailable` when it is not, cloud engines are `not_live`, and `image.ask` either answers from a vision model or fails with the configuration message. The provider key is not in the tool result or the proof log.

**Tests:** `libs/ar_domain/tests/unit/test_m33b_ocr_vision.py`. Checklist: [m33b-checklist](../testing/m33b-checklist.md).
