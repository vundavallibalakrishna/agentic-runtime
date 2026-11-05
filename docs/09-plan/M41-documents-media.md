# M41 — Documents and media

Goal: an agent makes and edits real office documents, and can generate images and transcribe audio with
models the tenant registers. New capability is a skill that drives the computer, not a tool for each format
([OQ-90](../open-questions.md)). Source:
[the tool review](../testing/tools-review-2026-11-05/tools-review.md), section B.

Depends on: M40. Tasks are split into full task entries when the milestone starts.

## M41-T01 PDF skill

**Do:** read with layout and tables, merge, split, fill a form, rasterise a page, and create with Unicode fonts.

## M41-T02 DOCX skill

**Do:** create from a template, edit a file in place, tracked changes and comments, and a redline.

## M41-T03 PPTX skill

**Do:** author a deck from a template with layouts, images, charts and notes. Render slides to images so the
model can check them.

## M41-T04 XLSX skill

**Do:** formulas, charts, styles and several sheets. Recalculate through LibreOffice. Read past the 5,000-row cap by paging.

## M41-T05 Extraction upgrades

**Do:** the library extractor keeps PDF tables, rasterises a scanned page before OCR, and takes the OCR
languages from tenant settings.

## M41-T06 Image generation

**Do:** `image.generate` and `image.edit` call a model of kind `image` that the tenant registers, on an
OpenAI-compatible images endpoint. The tools are off until one is set. The result is a file artifact.

## M41-T07 Audio

**Do:** `audio.transcribe` calls a registered transcription model. Off until one is set.

## M41-T08 Search

**Do:** a self-hosted search provider beside Brave and Tavily, and a recorded live search.
