"""Cover the general document tools the first suite left unexecuted."""

from __future__ import annotations

import asyncio
import io
import subprocess
import uuid
import zipfile
from types import SimpleNamespace

import pytest

from ar_common.errors import ArError, NotFoundError
from ar_domain.agents.access import Actor
from ar_domain.documents.library import DocumentLibrary
from ar_domain.identity.permissions import PERMISSION_KEYS


def test_section_map_errors_filters_and_follow_up_book(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.documents import sections as mod

    store = _store()
    actor = _actor()
    library = DocumentLibrary(store)
    saved = library.ingest(
        actor,
        data=b"# Hours\n\nThe desk opens at eight.\n\n# Other\n\nClosed on Sunday.\n",
        filename="hours.md",
    )
    run = _run(actor)
    store.runs = {run["id"]: run}
    store.conversations = {run["conversation_id"]: {"tenant_id": actor.tenant_id}}
    assert mod.pending_sections(store, run) is None
    assert mod.map_ready(run) is False
    with pytest.raises(ArError):
        mod.begin_map(store, run, {"documentIds": [str(saved["id"])], "cursor": ""})
    with pytest.raises(ArError):
        mod.begin_map(
            store,
            run,
            {
                "instruction": "Read it.",
                "documentIds": [str(saved["id"])],
                "outputSchema": "nope",
            },
        )
    with pytest.raises(ArError):
        mod.run_section(store, run, {"fileId": "f", "anchor": "p1-s0"})
    with pytest.raises(ArError):
        mod.deliver_map(store, run)
    odd = _run(actor)
    odd["checkpoint"] = []
    created = mod.begin_map(
        store, odd, {"instruction": "Read it.", "documentIds": [str(saved["id"])]}
    )
    assert created["sections"]
    assert isinstance(odd["checkpoint"], dict)
    with pytest.raises(ArError):
        mod.begin_map(
            store,
            run,
            {
                "instruction": "Say when it opens.",
                "documentIds": [str(saved["id"])],
                "heading": "No",
            },
        )
    first = mod.begin_map(
        store,
        run,
        {
            "instruction": "Say when it opens.",
            "documentIds": [str(saved["id"])],
            "cursor": "s:nope",
        },
    )
    again = mod.begin_map(
        store,
        run,
        {
            "instruction": "Say when it opens.",
            "documentIds": [str(saved["id"])],
            "cursor": "s:nope",
        },
    )
    assert again is first
    run["checkpoint"]["document_map"]["done"] = []
    section = first["sections"][0]

    def answer(store, run, job, section, text):  # type: ignore[no-untyped-def]
        del store, run, job, section
        return "eight" if text else ""

    monkeypatch.setattr(mod, "_read_model", answer)
    stored = mod.run_section(store, run, section)
    assert mod.run_section(store, run, section)["output"] == stored["output"]
    mod.run_pending(store, run)
    assert mod.map_ready(run)
    body = mod.deliver_map(store, run)
    assert body["results"]
    assert mod.pending_sections(store, run) is None
    run["checkpoint"]["document_map"]["sections"] = []
    with pytest.raises(ArError):
        mod.deliver_map(store, run)
    follow = _run(actor)
    follow["conversation_id"] = run["conversation_id"]
    mod.carry_outputs(store, follow)
    assert follow.get("document_reduction")
    mod.carry_outputs(SimpleNamespace(), follow)
    assert mod.tools_part({}) is None
    assert mod.tools_part({"tools_used": []}) is None
    assert mod.tools_part({"tools_used": ["documents.read"]}) == {
        "type": "reading",
        "tools": ["documents.read"],
    }
    narrowed = mod.begin_map(
        store,
        _run(actor),
        {
            "instruction": "Hours only.",
            "documentIds": [str(saved["id"])],
            "heading": "Hours",
            "pageFrom": 1,
            "pageTo": 1,
            "anchorFrom": "p1-s0",
            "anchorTo": "p9-s9",
        },
    )
    assert narrowed["sections"]
    bare = _run(actor)
    bare["tenant_id"] = "nope"
    with pytest.raises(ArError):
        mod.begin_map(store, bare, {"instruction": "Read.", "documentIds": [str(saved["id"])]})


def test_section_model_reads_schema_json_and_rejects_a_bad_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ar_domain.documents import sections as mod

    store = _store()
    actor = _actor()
    saved = DocumentLibrary(store).ingest(
        actor, data=b"The desk opens at eight.\n", filename="h.txt"
    )
    run = _run(actor)
    store.conversations = {}
    store.versions = {}
    schema = {"type": "object", "properties": {"when": {"type": "string"}}, "required": ["when"]}
    job = mod.begin_map(
        store,
        run,
        {
            "instruction": "When does it open?",
            "documentIds": [str(saved["id"])],
            "outputSchema": schema,
        },
    )
    section = job["sections"][0]
    answers = iter(
        [
            None,
            "not json",
            '```json\n{"when": 1}\n```',
            '```json\n{"when": "eight"}\n```',
            "Opens at eight.",
        ]
    )

    class Ask:
        def __init__(self, store: object, tenant: object, alias: str) -> None:
            del store, tenant, alias

        def __call__(self, task: str, evidence: str) -> str | None:
            del task, evidence
            return next(answers)

    monkeypatch.setattr("ar_domain.documents.model.ModelAsk", Ask)
    with pytest.raises(ArError):
        mod.run_section(store, run, section)
    run["checkpoint"]["document_map"]["done"] = {}
    with pytest.raises(ArError):
        mod.run_section(store, run, section)
    run["checkpoint"]["document_map"]["done"] = {}
    with pytest.raises(ArError):
        mod.run_section(store, run, section)
    run["checkpoint"]["document_map"]["done"] = {}
    parsed = mod.run_section(store, run, section)
    assert parsed["output"] == {"when": "eight"}
    host_plain = _run(actor)
    plain = mod.begin_map(
        store,
        host_plain,
        {"instruction": "When?", "documentIds": [str(saved["id"])]},
    )
    prose = mod.run_section(store, host_plain, plain["sections"][0])
    assert "eight" in str(prose["output"]).lower()
    empty = dict(plain["sections"][0])
    empty["text"] = "   "
    empty["anchor"] = "p9-s9"
    host = _run(actor)
    host["checkpoint"] = {
        "document_map": {
            "instruction": "When?",
            "sections": [empty],
            "done": {},
            "delivered": False,
        }
    }
    assert mod.run_section(store, host, empty)["output"] == ""
    broken = _run(actor)
    broken["checkpoint"] = {"document_map": {"instruction": "x", "sections": [section], "done": {}}}
    monkeypatch.setattr(
        "ar_domain.tools.agent_loop.model_alias_for",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("no model")),
    )
    with pytest.raises(ArError):
        mod._read_model(store, broken, broken["checkpoint"]["document_map"], section, "text")


def test_convert_reports_a_missing_tool_and_pages_archives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ar_domain.documents.convert import convert_and_extract
    from ar_domain.documents.extract import ExtractError

    with pytest.raises(ExtractError):
        convert_and_extract(b"x", "notes.exe", "application/octet-stream")
    with pytest.raises(ExtractError):
        convert_and_extract(b"x", "legacy.doc", "")
    with pytest.raises(ExtractError):
        convert_and_extract(b"x", "legacy.xls", "")
    with pytest.raises(ExtractError):
        convert_and_extract(b"not a zip", "bundle.zip", "application/zip")
    empty = io.BytesIO()
    with zipfile.ZipFile(empty, "w") as book:
        book.writestr("nested/", "")
    with pytest.raises(ExtractError):
        convert_and_extract(empty.getvalue(), "empty.zip", "application/zip")
    junk = io.BytesIO()
    with zipfile.ZipFile(junk, "w") as book:
        book.writestr("bad.pdf", b"%PDF-not-really")
    with pytest.raises(ExtractError):
        convert_and_extract(junk.getvalue(), "junk.zip", "application/zip")
    mixed = io.BytesIO()
    with zipfile.ZipFile(mixed, "w") as book:
        book.writestr("bad.pdf", b"%PDF-not-really")
        book.writestr("note.txt", "Hi")
        book.writestr("more.txt", "There")
        book.writestr("inner.zip", b"PK")
    monkeypatch.setattr(
        "ar_domain.documents.convert.get_settings",
        lambda: SimpleNamespace(document_zip_members=2, document_max_bytes=4),
    )
    paged = convert_and_extract(mixed.getvalue(), "mixed.zip", "application/zip")
    assert paged.passages
    monkeypatch.setattr("ar_domain.documents.convert.shutil.which", lambda _name: "/bin/soffice")
    monkeypatch.setattr(
        "ar_domain.documents.convert.blocking",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(cmd="soffice", timeout=1)
        ),
    )
    with pytest.raises(ExtractError):
        convert_and_extract(b"x", "legacy.odt", "")

    class Failed:
        returncode = 1

    monkeypatch.setattr("ar_domain.documents.convert.blocking", lambda *_a, **_k: Failed())
    with pytest.raises(ExtractError):
        convert_and_extract(b"x", "legacy.rtf", "")
    with pytest.raises(ExtractError):
        convert_and_extract(b"x", "legacy.msg", "")
    message = b"Subject: Hours\nFrom: ada@example.com\nContent-Type: text/html\n\n<p>Eight</p>\n"
    html = convert_and_extract(message, "note.eml", "message/rfc822")
    assert html.passages


def test_text_renderers_write_tables_lists_and_sheet_markdown() -> None:
    from ar_domain.documents.create.spec import parse
    from ar_domain.documents.create.textfmt import render_csv, render_html, render_markdown

    spec = parse(
        {
            "format": "md",
            "title": "Notes",
            "subtitle": "Board",
            "sections": [
                {
                    "heading": "One",
                    "level": 9,
                    "paragraphs": ["Hello"],
                    "bullets": ["Ada"],
                    "table": {"columns": ["n"], "rows": [["1"]]},
                }
            ],
        }
    )
    body = render_markdown(spec)
    assert b"Board" in body and b"| n |" in body
    html = render_html(spec)
    assert b"<li>Ada</li>" in html and b"<p>Board</p>" in html
    sheets = parse(
        {
            "format": "md",
            "title": "Grid",
            "sheets": [{"name": "A", "columns": ["n"], "rows": [["1"]]}],
        }
    )
    assert b"## A" in render_markdown(sheets)
    table = parse(
        {
            "format": "html",
            "title": "Grid",
            "sections": [
                {
                    "heading": "T",
                    "table": {"columns": ["n"], "rows": [["1"]]},
                }
            ],
        }
    )
    assert b"n" in render_csv(table)


def test_image_ask_rejects_a_missing_page_renderer() -> None:
    from ar_domain.documents.vision import VisionError
    from ar_domain.tools.vision import _render_page, _vision_alias, _what_next, dispatch_image

    store = _store()
    actor = _actor()
    assert dispatch_image(store, "crop", {})["is_error"] is True
    assert dispatch_image(store, "ask", {})["is_error"] is True
    args = {"_tenant_id": actor.tenant_id, "_user_id": actor.user_id, "question": ""}
    assert dispatch_image(store, "ask", args)["is_error"] is True
    saved = DocumentLibrary(store).ingest(actor, data=b"Hello page.\n", filename="page.txt")
    page = {
        **args,
        "question": "What is on the page?",
        "documentId": str(saved["id"]),
        "page": "nope",
    }
    assert dispatch_image(store, "ask", page)["is_error"] is True
    page["page"] = 1
    refused = dispatch_image(store, "ask", page)
    assert refused["is_error"] is True
    with pytest.raises(ArError):
        _render_page(b"%PDF-1.4", 1)
    with pytest.raises(ArError):
        _render_page(b"not a pdf", 1)
    assert "documents.ocr" in _what_next(VisionError("vision_unavailable", "No vision model."))
    assert _what_next(VisionError("validation_failed", "empty")) == "empty"
    assert _vision_alias(store, {"visionAlias": " eyes "}) == "eyes"
    version = uuid.uuid4()
    store.versions[version] = {
        "definition": {"model": {"visionAlias": "board-vision"}},
    }
    assert _vision_alias(store, {"_agent_version_id": version}) == "board-vision"
    missing = dispatch_image(
        store,
        "ask",
        {**args, "question": "Describe it.", "documentId": str(uuid.uuid4()), "page": 1},
    )
    assert missing["is_error"] is True


def test_library_scopes_cursors_grants_and_schema_extract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ar_domain.runs.request import ask

    store = _store()
    actor = _actor()
    other = Actor(actor.tenant_id, uuid.uuid4(), PERMISSION_KEYS)
    library = DocumentLibrary(store)
    body = "\n\n".join(
        f"# Heading {index}\n\nParagraph {index} about badges." for index in range(18)
    )
    saved = library.ingest(actor, data=body.encode(), filename="long.md")
    document_id = uuid.UUID(str(saved["id"]))
    row = store.library_documents[document_id]
    outline = library.outline(actor, document_id)
    assert outline["nextCursor"]
    assert library.outline(actor, document_id, cursor=str(outline["nextCursor"]))["outline"]
    listed = library.list_items(actor, cursor="o:nope")
    assert listed["total"] >= 1
    file_id = uuid.uuid4()
    store.files[file_id] = {
        "tenant_id": actor.tenant_id,
        "sha256": row["content_hash"],
        "filename": "long.md",
    }
    run = _run(actor)
    ask(run, "file_ids", [str(file_id)])
    ask(run, "collection_ids", [])
    turned = library.list_items(actor, scope="turn", run=run)
    assert turned["total"] == 1
    assert library.list_items(actor, scope="conversation", run=run)["total"] == 0
    passages = library.passages(actor, document_id, page_from=1, page_to=1)
    assert passages["passages"]
    tables = library.tables(actor, document_id, table="missing", offset=0, limit=2)
    assert tables["tables"] == []
    found = library.search(actor, "badges", document_ids=[str(document_id)], top_k=1, run=run)
    assert found["hits"]
    heading = str(row["passages"][0]["heading"])
    anchored = library.read(actor, document_id, heading=heading, anchor_from="p1-s0", limit=20)
    assert anchored["text"]
    with pytest.raises(ArError):
        library.read(actor, document_id, anchor="missing")
    original = library.original(actor, document_id)
    assert original
    row["content_hash"] = "0" * 64
    with pytest.raises(ArError):
        library.original(actor, document_id)
    row["content_hash"] = store.files[file_id]["sha256"]
    with pytest.raises(ArError):
        library.edit(actor, document_id, [])
    with pytest.raises(ArError):
        library.extract(actor, document_id, {})
    monkeypatch.setattr(
        "ar_domain.documents.model.ask_model",
        lambda *_args, **_kwargs: '{"when": "eight"}',
    )
    extracted = library.extract(
        actor,
        document_id,
        {"type": "object", "properties": {"when": {"type": "string"}}, "required": ["when"]},
    )
    assert extracted["result"]["when"] == "eight"
    monkeypatch.setattr(
        "ar_domain.documents.model.ask_model",
        lambda *_args, **_kwargs: "not-json",
    )
    with pytest.raises(ArError):
        library.extract(
            actor,
            document_id,
            {"type": "object", "properties": {"when": {"type": "string"}}},
        )
    version = uuid.uuid4()
    store.versions[version] = {
        "tenant_id": actor.tenant_id,
        "definition": {"knowledge": {"fileIds": [str(file_id)]}},
    }
    assert library.get(other, document_id)["id"] == str(document_id)
    row["owner_user_id"] = None
    with pytest.raises(NotFoundError):
        library.get(other, document_id)
    row["owner_user_id"] = actor.user_id
    collection = uuid.uuid4()
    store.knowledge_documents[uuid.uuid4()] = {
        "tenant_id": actor.tenant_id,
        "collection_id": str(collection),
        "version_hash": row["content_hash"],
        "status": "indexed",
    }
    mapped = library.rows_for_map(
        actor, run, document_ids=[], file_ids=[], collection_ids=[str(collection)]
    )
    assert mapped
    by_file = library.read(other, file_id, limit=50)
    assert by_file["text"]


def test_indexed_search_uses_the_knowledge_index(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store()
    actor = _actor()
    library = DocumentLibrary(store)
    saved = library.ingest(actor, data=b"Staff use badges at the door.\n", filename="a.txt")
    document_id = uuid.UUID(str(saved["id"]))
    row = store.library_documents[document_id]
    knowledge_id = uuid.uuid4()
    collection = uuid.uuid4()
    store.knowledge_documents[knowledge_id] = {
        "id": knowledge_id,
        "tenant_id": actor.tenant_id,
        "collection_id": collection,
        "version_hash": row["content_hash"],
        "status": "indexed",
        "raw_file_id": None,
        "library_document_id": str(document_id),
    }
    store.document_chunks[uuid.uuid4()] = {"document_id": knowledge_id}
    monkeypatch.setattr(
        "ar_domain.knowledge.searching.search",
        lambda *_a, **_k: {"hits": [{"anchor": "p1-s0", "snippet": "badges", "score": 0.9}]},
    )
    found = library.search(
        actor,
        "badges",
        document_ids=[str(document_id)],
        collection_ids=[str(collection)],
    )
    assert found["hits"]
    monkeypatch.setattr(
        "ar_domain.knowledge.searching.search",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("down")),
    )
    lexical = library.search(actor, "badges")
    assert lexical["hits"]


def test_dispatch_map_extract_edit_and_pack_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.tools.documents import (
        _claim_text,
        _crosscheck_text,
        _field_text,
        _rewrite_text,
        _rule_set,
        _statements,
        dispatch_documents,
        register_document_tool,
    )

    store = _store()
    actor = _actor()
    saved = DocumentLibrary(store).ingest(actor, data=b"# One\n\nAlpha.\n", filename="note.md")
    run = _run(actor)
    store.runs[run["id"]] = run
    store.conversations[run["conversation_id"]] = {}
    base = {"_tenant_id": actor.tenant_id, "_user_id": actor.user_id, "_run_id": run["id"]}
    assert dispatch_documents(store, "map", {**base, "instruction": "Read."})["is_error"] is True
    monkeypatch.setattr(
        "ar_domain.documents.sections._read_model",
        lambda *_a, **_k: "Alpha.",
    )
    mapped = dispatch_documents(
        store,
        "map",
        {**base, "instruction": "Read it.", "documentIds": [str(saved["id"])]},
    )
    assert mapped["is_error"] is False
    assert dispatch_documents(store, "map", {"instruction": "Read."})["is_error"] is True
    monkeypatch.setattr(
        "ar_domain.documents.model.ask_model",
        lambda *_a, **_k: '{"note": "alpha"}',
    )
    extracted = dispatch_documents(
        store,
        "extract",
        {
            **base,
            "documentId": str(saved["id"]),
            "schema": {"type": "object", "properties": {"note": {"type": "string"}}},
        },
    )
    assert extracted["is_error"] is False
    assert _field_text({"result": {"note": "alpha"}})
    assert _field_text({}) == ""
    edited = dispatch_documents(
        store,
        "edit",
        {
            **base,
            "documentId": str(saved["id"]),
            "redline": True,
            "changes": [{"anchor": "p1-s0", "text": "Beta."}],
        },
    )
    assert edited["is_error"] is False
    register_document_tool("ping", lambda _store, _args: {"text": "pong", "is_error": False})
    assert dispatch_documents(store, "ping", base)["text"] == "pong"
    register_document_tool("drop", lambda _store, _args: "nope")
    assert dispatch_documents(store, "drop", base)["is_error"] is True
    assert _statements({"requirements": "one\n\ntwo"}) == ["one", "two"]
    assert _rule_set({"rule_set": {"id": "a"}}) == {"id": "a"}
    assert "anchor" in _claim_text({"claims": [{"text": "Alpha", "anchor": "p1-s0", "page": 1}]})
    assert "does not contain" in _claim_text({})
    assert "hours differ" in _crosscheck_text(
        {
            "title": "Note",
            "passagesRead": 2,
            "discarded": 1,
            "findings": [
                {
                    "kind": "value_mismatch",
                    "statement": "hours differ",
                    "quotes": [{"anchor": "p1-s0", "page": 1, "quote": "eight"}],
                }
            ],
        }
    )
    assert "No disagreement" in _crosscheck_text({"title": "Note", "passagesRead": 1})
    assert "preview" in _rewrite_text({"id": "r", "hunks": [{}]})
    searched = dispatch_documents(
        store,
        "search",
        {**base, "query": "Alpha", "documentIds": str(saved["id"]), "topK": "1"},
    )
    assert searched["is_error"] is False
    read = dispatch_documents(
        store,
        "read",
        {**base, "documentId": str(saved["id"]), "heading": "One", "anchorFrom": "p1-s0"},
    )
    assert read["is_error"] is False


def test_lifecycle_reprocess_sweep_and_cascade() -> None:
    from ar_domain.documents.lifecycle import (
        delete_file_cascade,
        delete_library,
        reprocess,
        sweep_expired,
    )

    store = _store()
    actor = _actor()
    library = DocumentLibrary(store)
    saved = library.ingest(actor, data=b"Staff use badges.\n", filename="policy.txt")
    document_id = uuid.UUID(str(saved["id"]))
    again = reprocess(store, actor, document_id)
    assert again["id"] == str(document_id)
    file_id = uuid.uuid4()
    digest = store.library_documents[document_id]["content_hash"]
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": actor.tenant_id,
        "owner_user_id": actor.user_id,
        "sha256": digest,
        "status": "ready",
        "retention_until": "2000-01-01",
    }
    store.blobs[file_id] = b"Staff use badges.\n"
    assert sweep_expired(store) == 1
    assert document_id not in store.library_documents
    kept = library.ingest(actor, data=b"Visitors sign the book.\n", filename="visitors.txt")
    kept_id = uuid.UUID(str(kept["id"]))
    other = uuid.uuid4()
    store.files[other] = {
        "id": other,
        "tenant_id": actor.tenant_id,
        "sha256": store.library_documents[kept_id]["content_hash"],
        "status": "ready",
    }
    delete_file_cascade(
        store,
        actor.tenant_id,
        actor.user_id,
        {"id": uuid.uuid4(), "sha256": store.files[other]["sha256"]},
    )
    assert kept_id in store.library_documents
    delete_library(store, actor, kept_id)
    assert kept_id not in store.library_documents
    assert sweep_expired(SimpleNamespace(files="nope")) == 0


def test_binding_measures_files_and_agent_grants() -> None:
    from ar_domain.documents.binding import (
        bind_turn,
        context_window_for,
        remember_task,
        turn_has_documents,
    )
    from ar_domain.loop.planning import planning_enabled

    store = _store()
    actor = _actor()
    saved = DocumentLibrary(store).ingest(actor, data=b"# Access\n\nBadges.\n", filename="a.md")
    document_id = uuid.UUID(str(saved["id"]))
    row = store.library_documents[document_id]
    file_id = uuid.uuid4()
    store.files[file_id] = {
        "tenant_id": actor.tenant_id,
        "owner_user_id": actor.user_id,
        "status": "ready",
        "sha256": row["content_hash"],
        "size_bytes": 12,
        "filename": "a.md",
    }
    files, named, items, schema, text = bind_turn(
        store,
        tenant_id=actor.tenant_id,
        user_id=actor.user_id,
        attachment_ids=[],
        file_ids=[file_id, file_id],
        collection_ids=[],
        instruction="List the controls.",
        task_template="",
        items=[{"id": "1", "text": "Badges"}],
        response_format=None,
        context_window=8192,
        definition={"knowledge": {"fileIds": [str(file_id)]}},
    )
    assert files == [file_id]
    assert named[0].title == "Access"
    assert named[0].tokens > 0
    assert items[0]["text"] == "Badges"
    assert schema is None
    assert "controls" in text
    run = _run(actor)
    remember_task(
        store,
        run,
        tenant_id=actor.tenant_id,
        user_id=actor.user_id,
        file_ids=[file_id],
        collection_ids=[],
        items=["Badges"],
        template_id="",
    )
    assert turn_has_documents(store, run, None) is True
    stranger = uuid.uuid4()
    granted = bind_turn(
        store,
        tenant_id=actor.tenant_id,
        user_id=stranger,
        attachment_ids=[],
        file_ids=[file_id],
        collection_ids=[],
        instruction="Read.",
        task_template="",
        items=[],
        response_format=None,
        context_window=None,
        definition={"knowledge": {"fileIds": [str(file_id)]}},
    )
    assert granted[0] == [file_id]
    pending = uuid.uuid4()
    store.files[pending] = {
        "tenant_id": actor.tenant_id,
        "owner_user_id": actor.user_id,
        "status": "pending",
        "sha256": "abc",
    }
    with pytest.raises(ArError):
        bind_turn(
            store,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            attachment_ids=[pending],
            file_ids=[],
            collection_ids=[],
            instruction="",
            task_template="",
            items=[],
            response_format=None,
            context_window=None,
            definition=None,
        )
    assert context_window_for(store, actor.tenant_id, run) is None
    assert planning_enabled(None, documents=True) is True
    assert planning_enabled({"planning": {"enabled": False}}, documents=True) is False
    assert planning_enabled({}, documents=False) is False


def test_grounding_fallbacks_and_citation_tables() -> None:
    from ar_domain.documents.chunk import retrieve
    from ar_domain.documents.cited import _anchored, _attached_documents, _passage
    from ar_domain.documents.grounding import line_hunks, table_items

    document = {
        "id": "d",
        "title": "Hours",
        "passages": [
            {
                "anchor": "p1-s0",
                "page": 1,
                "heading": "Hours",
                "text": "Owner: Ada\n- File the return",
            },
        ],
        "tables": [{"anchor": "t1", "csv_text": "item,owner", "page": 1, "text": ""}],
    }
    assert line_hunks("a\nb", "a\nc")
    assert table_items("rows.csv", b"name,note\nAda,File the return\n")
    assert _attached_documents(SimpleNamespace(), {}) == []
    found = _passage([document], "t1", {"item"})
    assert found is not None
    assert any(row.get("anchor") == "t1" for row in _anchored(document))
    long = "alpha " * 50
    clipped = retrieve(
        [{"text": long, "page": 1, "anchor": "p1"}, {"text": "beta", "page": 2, "anchor": "p2"}],
        "alpha",
        budget=12,
    )
    assert len(str(clipped[0]["text"])) <= 12
    assert retrieve([{"text": "", "page": 1, "anchor": "p1"}], "zzzz", budget=5)


def test_created_pdf_and_slides_round_trip_through_the_extractor() -> None:
    from ar_domain.documents.create.render import render
    from ar_domain.documents.create.spec import parse
    from ar_domain.documents.extract import extract_bytes

    brief = {
        "title": "Hours",
        "subtitle": "Desk",
        "sections": [
            {
                "heading": "Open",
                "paragraphs": ["The desk opens at eight."],
                "bullets": ["Weekdays"],
            }
        ],
    }
    for fmt in ("pdf", "pptx", "docx", "html"):
        data = render(parse({**brief, "format": fmt}))
        extracted = extract_bytes(data, filename=f"hours.{fmt}")
        assert extracted.passages


def test_create_and_extract_reject_bad_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    import math

    from ar_domain.documents.create.spec import CreateError, parse
    from ar_domain.documents.extract import ExtractError, extract_bytes
    from ar_domain.documents.lifecycle import delete_library, reprocess, sweep_expired

    with pytest.raises(CreateError):
        parse({"format": "md", "title": ""})
    with pytest.raises(CreateError):
        parse({"format": "md", "title": "T", "sections": "nope"})
    with pytest.raises(CreateError):
        parse({"format": "xlsx", "title": "T", "sheets": ["nope"]})
    with pytest.raises(CreateError):
        parse(
            {
                "format": "md",
                "title": "T",
                "sections": [{"heading": "A", "table": "nope"}],
            }
        )
    with pytest.raises(CreateError):
        parse(
            {
                "format": "md",
                "title": "T",
                "sections": [{"heading": "A", "table": {"rows": "nope"}}],
            }
        )
    with pytest.raises(CreateError):
        parse(
            {
                "format": "md",
                "title": "T",
                "sections": [{"heading": "A", "bullets": 3}],
            }
        )
    with pytest.raises(CreateError):
        parse(
            {
                "format": "md",
                "title": "T",
                "sections": [{"heading": "A", "table": {"columns": ["n"], "rows": ["x"]}}],
            }
        )
    wide = parse(
        {
            "format": "xlsx",
            "title": "Grid",
            "filename": "grid.bin",
            "sheets": [
                {
                    "name": "A/B",
                    "rows": [[{"n": True}, {"n": False}, {"n": math.nan}]],
                },
                {"name": "A B", "columns": ["n"], "rows": [[{"n": 1.5}]]},
            ],
        }
    )
    assert wide.sheets
    prose = parse(
        {
            "format": "xlsx",
            "title": "Notes",
            "sections": [{"heading": "One", "paragraphs": ["Hello"], "bullets": ["Ada"]}],
        }
    )
    assert any(sheet.name == "Notes" for sheet in prose.sheets)
    slides = parse(
        {
            "format": "pptx",
            "title": "Deck",
            "sheets": [{"name": "Only", "columns": ["n"], "rows": [["1"]]}],
        }
    )
    assert slides.sections
    with pytest.raises(ExtractError):
        extract_bytes(b"not a docx", filename="note.docx")
    with pytest.raises(ExtractError):
        extract_bytes(b"", filename="empty.csv")
    with pytest.raises(ExtractError):
        extract_bytes(b"\x89PNG\r\n", filename="scan.png")

    store = _store()
    actor = _actor()
    saved = DocumentLibrary(store).ingest(actor, data=b"Staff use badges.\n", filename="p.txt")
    document_id = uuid.UUID(str(saved["id"]))
    row = store.library_documents[document_id]
    knowledge_id = uuid.uuid4()
    store.knowledge_documents[knowledge_id] = {
        "id": knowledge_id,
        "tenant_id": actor.tenant_id,
        "version_hash": row["content_hash"],
        "status": "indexed",
        "raw_file_id": None,
    }
    dropped: list[object] = []

    def drop(_store: object, document: dict[str, object], *, actor_id: object) -> None:
        del _store, actor_id
        dropped.append(document["id"])

    monkeypatch.setattr("ar_domain.knowledge.syncing.delete_document", drop)
    delete_library(store, actor, document_id)
    assert dropped == [knowledge_id]
    stranger = Actor(actor.tenant_id, uuid.uuid4(), PERMISSION_KEYS)
    again = DocumentLibrary(store).ingest(actor, data=b"Visitors sign in.\n", filename="v.txt")
    with pytest.raises(NotFoundError):
        reprocess(store, stranger, uuid.UUID(str(again["id"])))
    stale = uuid.uuid4()
    store.files[stale] = {
        "id": stale,
        "status": "deleted",
        "retention_until": "2000-01-01",
        "tenant_id": actor.tenant_id,
        "owner_user_id": actor.user_id,
    }
    nameless = uuid.uuid4()
    store.files[nameless] = {"retention_until": "2000-01-01", "status": "ready"}
    assert sweep_expired(store) == 0


def test_more_extract_library_and_lifecycle_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.documents.extract import ExtractError, _title_from, _xml, extract_bytes, sniff
    from ar_domain.documents.library import _extract_error, _rewrite_view
    from ar_domain.documents.lifecycle import _bytes, _drop_raw, _reader, _reindex

    headed = extract_bytes(b"Intro line\n\n# Next\n\nThe body.\n\n# Tail\n", filename="note.txt")
    assert headed.passages
    html = (
        b"<!doctype html><html><body><h1>Hours</h1><p>Eight</p>"
        b"<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>"
        b"</body></html>"
    )
    assert extract_bytes(html, filename="page.bin").tables
    assert sniff(b"RIFFxxxxWEBP", "a.bin", "") == "image"
    assert sniff(b"hello", "book.xlsx", "") == "xlsx"
    assert sniff(b"\x00\x00", "a.bin", "text/plain") == "txt"
    assert sniff(b"PK\x03\x04nope", "a.bin", "") == ""
    with pytest.raises(ExtractError):
        extract_bytes(b"   \n", filename="blank.txt")
    with pytest.raises(ExtractError):
        _xml(b"<not")
    assert _title_from([]) == "Document"

    class Failed:
        returncode = 1
        stdout = b""

    monkeypatch.setattr(
        "ar_domain.documents.extract.shutil.which",
        lambda name: "/bin/tesseract" if name == "tesseract" else None,
    )
    monkeypatch.setattr("ar_domain.documents.extract.blocking", lambda *_a, **_k: Failed())
    with pytest.raises(ExtractError):
        extract_bytes(b"\x89PNG\r\n\x1a\n", filename="scan.png")

    store = _store()
    actor = _actor()
    library = DocumentLibrary(store)
    monkeypatch.setattr("ar_domain.documents.library.scan_bytes", lambda *_a, **_k: "infected")
    with pytest.raises(ArError):
        library.ingest(actor, data=b"nope\n", filename="bad.txt")
    monkeypatch.setattr("ar_domain.documents.library.scan_bytes", lambda *_a, **_k: "error")
    with pytest.raises(ArError):
        library.ingest(actor, data=b"nope\n", filename="bad.txt")
    monkeypatch.setattr("ar_domain.documents.library.scan_bytes", lambda *_a, **_k: "clean")
    saved = library.ingest(actor, data=b"Staff use badges.\n", filename="p.txt")
    document_id = uuid.UUID(str(saved["id"]))
    row = store.library_documents[document_id]
    row["object_key"] = ""
    again = library.ingest(actor, data=b"Staff use badges.\n", filename="p.txt")
    assert again["deduped"] is True
    with pytest.raises(ArError):
        library.ingest(actor, data=b"x", filename="x.txt", extracted="nope")  # type: ignore[arg-type]
    monkeypatch.setattr(
        "ar_domain.documents.model.ask_model",
        lambda *_a, **_k: '{"when": 1}',
    )
    with pytest.raises(ArError):
        library.extract(
            actor,
            document_id,
            {"type": "object", "properties": {"when": {"type": "string"}}, "required": ["when"]},
        )
    store.originals = {}
    with pytest.raises(NotFoundError):
        library.original(actor, document_id)
    assert _extract_error(ExtractError("unsupported", "no")).code.value == "unsupported_media_type"
    assert _extract_error(ExtractError("too_many_pages", "no")).code.value == "payload_too_large"
    assert _extract_error(ExtractError("corrupt", "no")).code.value == "validation_failed"
    assert _rewrite_view({"id": "1", "document_id": document_id, "hunks": []})["kind"] == "rewrite"
    file_id = uuid.uuid4()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": actor.tenant_id,
        "sha256": row["content_hash"],
    }
    knowledge_id = uuid.uuid4()
    store.knowledge_documents[knowledge_id] = {
        "id": knowledge_id,
        "tenant_id": actor.tenant_id,
        "raw_file_id": file_id,
        "version_hash": "other",
        "status": "indexed",
    }
    called: list[object] = []

    async def _ingest(_store: object, found: uuid.UUID, _raw: bytes) -> str:
        called.append(found)
        return "indexed"

    monkeypatch.setattr("ar_domain.knowledge.pipeline.ingest_or_enqueue", _ingest)
    asyncio.run(_reindex(store, actor, row))
    assert called == [knowledge_id]
    assert _bytes(store, row) == b""
    monkeypatch.setattr(
        "ar_domain.knowledge.syncing.delete_document",
        lambda *_a, **_k: called.append("drop"),
    )
    _drop_raw(store, file_id, actor_id=actor.user_id)
    assert _reader(store, actor, "vision") is not None
    assert _reader(store, actor, "") is None
    store.audit_log = None
    library._audit(actor, "library_document.ingested", document_id, {})


def test_ocr_refusals_section_helpers_and_page_render(monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import Path

    from ar_domain.documents import sections as sections_mod
    from ar_domain.tools.documents import _id_list, _run, _strings, _table_text, dispatch_documents
    from ar_domain.tools.vision import _render_page

    store = _store()
    actor = _actor()
    saved = DocumentLibrary(store).ingest(actor, data=b"Hello.\n", filename="a.txt")
    base = {"_tenant_id": actor.tenant_id, "_user_id": actor.user_id}
    unknown = dispatch_documents(store, "ocr", {**base, "engine": "nope"})
    assert unknown["is_error"] is True
    cloud = dispatch_documents(
        store, "ocr", {**base, "engine": "aws_textract", "fileId": str(uuid.uuid4())}
    )
    assert cloud["is_error"] is True
    stored = dispatch_documents(
        store, "ocr", {**base, "documentId": str(saved["id"]), "engine": "local"}
    )
    assert stored["is_error"] is False
    assert _strings(None) == []
    assert _strings(["", "kept"]) == ["kept"]
    assert _id_list(None) == []
    assert _id_list([" a "]) == ["a"]
    assert _table_text("none") == "No tables."
    run = _run(store, {})
    assert run is None
    run_id = uuid.uuid4()
    store.runs = {run_id: {"id": run_id}}
    assert _run(store, {"_run_id": str(run_id)}) is not None
    assert _run(store, {"_run_id": "not-a-uuid"}) is None
    assert sections_mod._int(True) == 0
    assert sections_mod._int("nope") == 0
    assert sections_mod._int(4) == 4
    assert sections_mod._int(1.2) == 0
    assert sections_mod._ids("  ") == []
    assert sections_mod.tools_part({"tools_used": [""]}) is None
    monkeypatch.setattr(sections_mod, "_alias", lambda *_a, **_k: "")
    with pytest.raises(ArError):
        sections_mod._read_model(store, _run_row(actor), {}, {"anchor": "p1"}, "text")
    bad = _run_row(actor)
    bad["tenant_id"] = "nope"
    monkeypatch.setattr(sections_mod, "_alias", lambda *_a, **_k: "reasoning")
    with pytest.raises(ArError):
        sections_mod._read_model(store, bad, {}, {"anchor": "p1"}, "text")

    def fake_run(cmd: list[str], **_kwargs: object) -> object:
        target = cmd[-1]
        page = cmd[cmd.index("-f") + 1]
        Path(f"{target}-{page}.png").write_bytes(b"\x89PNG\r\n")

        class Done:
            returncode = 0

        return Done()

    monkeypatch.setattr("shutil.which", lambda _name: "/bin/pdftoppm")
    monkeypatch.setattr("subprocess.run", fake_run)
    rendered = _render_page(b"%PDF-1.4", 1)
    assert rendered.startswith(b"\x89PNG")


def test_create_limits_and_heading_pages() -> None:
    from ar_domain.documents.create.spec import CreateError, parse
    from ar_domain.documents.extract import ExtractError, extract_bytes

    with pytest.raises(CreateError):
        parse({"format": "md", "title": "T", "sections": [{}] * 41})
    with pytest.raises(CreateError):
        parse({"format": "xlsx", "title": "T", "sheets": [{}] * 13})
    titled = parse(
        {
            "format": "md",
            "title": "A\x01B",
            "sections": [{"level": True, "paragraphs": "one line"}],
        }
    )
    assert "A" in titled.title
    with pytest.raises(ExtractError):
        extract_bytes(b"# Only a heading\n", filename="empty-body.md")


def test_originals_quality_and_retrieval_edges() -> None:
    from ar_common.errors import ArError
    from ar_common.s3 import ObjectStoreError
    from ar_domain.documents.chunk import retrieve
    from ar_domain.documents.originals import read_original, store_original
    from ar_domain.documents.quality import engine_name, quality_record

    class Down:
        def put(self, *_args: object, **_kwargs: object) -> None:
            raise ObjectStoreError("down")

        def get(self, *_args: object, **_kwargs: object) -> None:
            raise ObjectStoreError("down")

    class Text:
        def get(self, *_args: object, **_kwargs: object) -> str:
            return "not-bytes"

    store = SimpleNamespace(objects=Down())
    with pytest.raises(ArError):
        store_original(
            store,
            tenant_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            data=b"hi",
            media_type="text/plain",
        )
    with pytest.raises(ArError):
        read_original(store, "library/key")
    assert read_original(SimpleNamespace(objects=Text()), "library/key") is None
    assert read_original(SimpleNamespace(), "") is None
    record = quality_record(
        page_count=1,
        passages=[{"text": "\ufffd"}],
        tables=[],
        pages_ocr=1,
        engine="vision",
    )
    assert "low_text" in record["warnings"]
    assert "mixed_encoding" in record["warnings"]

    class VisionOcr:
        pass

    assert engine_name(VisionOcr()) == "vision"
    clipped = retrieve(
        [
            {"text": "alpha", "page": 1, "anchor": "a"},
            {"text": "gamma " * 40, "page": 2, "anchor": "b"},
        ],
        "alpha gamma",
        budget=12,
    )
    assert clipped
    assert retrieve([{"text": "hello", "page": 1, "anchor": "a"}], "", budget=5)


def _run_row(actor: Actor) -> dict[str, object]:
    return _run(actor)


def _store() -> SimpleNamespace:
    return SimpleNamespace(
        library_documents={},
        files={},
        blobs={},
        audit_log=[],
        scanner="none",
        versions={},
        knowledge_documents={},
        knowledge_collections={},
        document_chunks={},
        runs={},
        conversations={},
        messages={},
    )


def _actor() -> Actor:
    return Actor(uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS)


def _run(actor: Actor) -> dict[str, object]:
    return {
        "id": uuid.uuid4(),
        "tenant_id": actor.tenant_id,
        "user_id": actor.user_id,
        "conversation_id": uuid.uuid4(),
        "checkpoint": {},
        "request": {},
    }
