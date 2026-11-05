# M33b checklist

OCR on a scanned page is a tool. `image.ask` answers a question about a picture. Labels below are what this proof actually ran.

## Golden OCR strings

Fixture directory: `docs/testing/fixtures/m33b/`.

| File | Role |
|---|---|
| `ocr-canary.png` | Image with known text |
| `ocr-canary.pdf` | One-page scanned PDF. The page image is that PNG. There is no text layer |
| `ocr-canary.expected.txt` | Golden strings, one per line |

The golden strings are:

```text
M33B CANARY
CODE 4821
```

A pass means both strings appear in the OCR text after whitespace is collapsed.

## What is built

| Path | Behaviour |
|---|---|
| `documents.ocr` | Reads a `fileId`, workspace path, or URL with local tesseract and stores the extraction. `documentId` alone returns text already stored. Another tenant receives not found |
| `image.ask` | One question about a PNG, JPEG, GIF or WebP. A PDF is refused and the caller is sent to `documents.ocr` |
| Assistant | The published assistant definition includes the `image` server. An older assistant that already includes `documents` is granted `image.ask` on startup |

The API image and the ingest image install `tesseract-ocr` and `tesseract-ocr-eng`. A process started from the repo without those packages still returns `ocr_unavailable`.

## Labels

| Engine | This proof | How to turn it on |
|---|---|---|
| tesseract | **live** | `tesseract` on `PATH` (`tesseract-ocr` and `tesseract-ocr-eng`). No provider key |
| Google Document AI | **not_live** | Not wired. Install tesseract instead. The tool returns `not_live` and does not call Google |
| Amazon Textract | **not_live** | Not wired. Same operator path as Google |
| Azure Document Intelligence | **not_live** | Not wired. Same operator path as Google |
| `image.ask` against `Qwen/Qwen2.5-VL-32B-Instruct` | **live** | Vision alias pointed at a vision-capable model. The provider key is sealed the same way as chat |
| Default seeded `vision` alias | **not_live** | `make seed` points `vision` at fake-llm. `image.ask` returns `vision_unavailable` until an operator replaces that alias |

`AR_VISION_MODEL` is read only by `scripts/m33b_proof.py`. The product uses the tenant's vision alias, not that variable.

## What the automated tests cover

`libs/ar_domain/tests/unit/test_m33b_ocr_vision.py`

- The fixture files exist and the golden file is the two strings above.
- Cloud engines are `not_live` and name the tesseract packages. A cloud call does not store the file.
- A stub OCR stores both golden strings. Another tenant gets not found.
- The scanned PDF sends the embedded JPEG to OCR.
- With tesseract installed, the PNG and the PDF both match the golden strings. Without it, that test skips and a separate test expects `ocr_unavailable`.
- The assistant catalogue lists `documents.ocr` and `image.ask`.
- Fake-llm `vision` returns `vision_unavailable`. A text model (`Qwen/Qwen3-32B`) does too, and names the model.
- A vision model call sends an `image_url` data URL. The sealed key is on the request header and is replaced in the answer. The pipeline preview does not contain the key.

## Live proof

Command: `uv run python scripts/m33b_proof.py`

The key is read from `AR_CERT_LLM_API_KEY` and is not written here. Result on 2026-11-05:

- tesseract **live**. `ocr-canary.png` PASS. `ocr-canary.pdf` PASS. Both golden strings were present.
- `google_document_ai`, `aws_textract` and `azure_document_intelligence` **not_live**.
- Vision model `Qwen/Qwen2.5-VL-32B-Instruct` on DeepInfra **PASS**. The answer contained the canary code. The key was not in the proof output.

A stock dev tenant still has the `vision` alias on fake-llm. Chat keeps working. `image.ask` stays `vision_unavailable` until that alias is a vision model with a sealed key.

## How to test on a laptop

1. `make bootstrap && make dev`.
2. Dev login as `admin@dev.local` (password `dev-password` from the realm export).
3. Open Documents. Upload `docs/testing/fixtures/m33b/ocr-canary.png`. The passage text contains `M33B CANARY` and `CODE 4821` when tesseract is installed. Without it, the upload error says OCR is not installed.
4. Upload `ocr-canary.pdf`. The same two strings appear. The PDF has no text layer, so this is the OCR path.
5. In chat with the assistant, ask it to call `documents.ocr` on that file and `image.ask` with "What code is printed?". OCR answers from the stored text. `image.ask` says vision is not configured until the vision alias is a vision model.
