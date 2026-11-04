# M24 checklist

Proof date: 2026-11-04. Model: Qwen/Qwen3-32B through DeepInfra (`https://api.deepinfra.com/v1/openai`). The provider key was read from `AR_CERT_LLM_API_KEY` at runtime and is not in this file.

Isolated Postgres was `127.0.0.1:55448`. The API listened on `18124`. Temporal was pointed at a closed port so the turn stayed in this process. The operator Postgres on 5432 and the processes on 8000, 8001 and 8013 were not used.

Public files:

- GNU GPL 3.0 and GPL 2.0 (gnu.org)
- RFC 9110 (rfc-editor.org), which names the authors
- NIST SP 800-53 Rev. 5 PDF, 492 pages (nvlpubs.nist.gov)

- [x] After the API process was replaced, the library still listed four documents, including the NIST PDF at 492 pages
- [x] `documents.summarise` on GPL 3 used the model (`modelUsed: true`) and returned 10 claims. Each quote is a substring of the license, including "Free software refers to freedom, not price."
- [x] `documents.compare` of GPL 3 against GPL 2 reported 22 added, 38 removed and 3 changed passages with anchors
- [x] `documents.check` used the model. "You may convey verbatim copies of the Program's source code" was `met` with a citation. "The organisation shall operate a colony on Mars" was `not_found` with no citation
- [x] `documents.gaps` repeated that the Mars requirement has no supporting passage
- [x] `documents.rewrite` proposed one hunk that rephrased the GPL opening in simpler words. The row stayed `proposed` until a reviewer accepted it. The accept call then returned `accepted`
- [x] Redaction of RFC 9110 removed `@` addresses. The preview names authors as `[PERSON]` and does not contain the original addresses
- [x] A page range of the 492-page PDF returned 14 passages for pages 40–42. The whole file was not sent to the model. Retrieval of a 300-page passage list stays inside 12,000 characters in the unit test
- [x] In chat, the agent called `documents.summarise`, `documents.compare` and `documents.check`. For the Mars requirement it answered that the document does not contain that passage
- [x] Playwright screenshots: library, document, comparison, check and rewrite, light and dark, desktop and mobile. Walkthrough: `walkthrough.webm`

Unit tests reject an encrypted PDF, a corrupt file, an oversized file and an infected upload.
