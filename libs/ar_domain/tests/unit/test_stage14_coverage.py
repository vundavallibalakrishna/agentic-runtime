"""Cover the Stage 14 paths the certification suite does not already execute."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from ar_common.errors import ArError, ErrorCode
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatBehaviour, _same_conversation
from ar_domain.conversations.triggers import previous_trigger_check_sql
from ar_domain.documents.library import _install_library_row, _load_library_hash, ingest_bytes
from ar_domain.durable.flush import _adopt_library_rows
from ar_domain.durable.m24 import library_id_for_hash
from ar_domain.durable.tracking import TrackedDict
from ar_domain.models.embedding import EmbeddingUnconfiguredError
from ar_domain.workspace.turn import _append_system, _retrieve


def test_previous_trigger_list_has_no_research() -> None:
    assert "'research'" not in previous_trigger_check_sql()
    assert "'eval'" in previous_trigger_check_sql()


def test_unknown_trigger_is_rejected_before_a_run_is_stored() -> None:
    service = ChatBehaviour()
    with pytest.raises(ArError) as caught:
        service._new_run(
            uuid.uuid4(),
            uuid.uuid4(),
            {},
            uuid.uuid4(),
            message_id=uuid.uuid4(),
            trigger="not-a-trigger",
        )
    assert caught.value.code == ErrorCode.VALIDATION_FAILED
    assert service.runs == {}


def test_file_without_a_conversation_uses_its_run() -> None:
    conversation_id = uuid.uuid4()
    run_id = uuid.uuid4()
    store = SimpleNamespace(runs={run_id: {"conversation_id": conversation_id}})
    assert _same_conversation(store, {"run_id": run_id}, conversation_id)
    assert not _same_conversation(store, {"run_id": run_id}, uuid.uuid4())
    assert not _same_conversation(store, {"conversation_id": None, "run_id": None}, conversation_id)


def test_api_port_override_must_be_a_port(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_common.host_ports import api_listen_port

    monkeypatch.setenv("AR_API_PORT", "18010")
    assert api_listen_port() == 18010
    monkeypatch.setenv("AR_API_PORT", "nope")
    with pytest.raises(ValueError, match="integer"):
        api_listen_port()
    monkeypatch.setenv("AR_API_PORT", "70000")
    with pytest.raises(ValueError, match="65535"):
        api_listen_port()


def test_install_skips_a_store_without_a_document_map() -> None:
    store = SimpleNamespace(library_documents=None, reloading=False)
    _install_library_row(store, {"id": uuid.uuid4()})
    assert store.library_documents is None


def test_install_clears_the_dirty_bit_on_a_loaded_row() -> None:
    store = SimpleNamespace(reloading=False)
    documents = TrackedDict(store, "library_documents")
    store.library_documents = documents
    document_id = uuid.uuid4()
    documents.dirty.add(document_id)
    _install_library_row(
        store,
        {"id": document_id, "title": "Loaded", "status": "ready"},
    )
    assert document_id not in documents.dirty
    assert documents[document_id]["title"] == "Loaded"


def test_hash_lookup_handles_a_blank_digest_and_a_string_id() -> None:
    class _Result:
        def __init__(self, row: object) -> None:
            self._row = row

        def first(self) -> object:
            return self._row

    class _Session:
        async def execute(self, _statement: object, _params: object = None) -> _Result:
            return _Result(("11111111-1111-4111-8111-111111111111",))

    session = _Session()
    tenant_id = uuid.uuid4()
    assert asyncio.run(library_id_for_hash(session, tenant_id, "")) is None  # type: ignore[arg-type]
    found = asyncio.run(library_id_for_hash(session, tenant_id, "abc"))  # type: ignore[arg-type]
    assert found == uuid.UUID("11111111-1111-4111-8111-111111111111")


def test_durable_hash_is_reused_and_a_missing_object_is_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    document_id = uuid.uuid4()
    data = b"stage14-bytes"
    import hashlib

    digest = hashlib.sha256(data).hexdigest()
    loaded = {
        "id": document_id,
        "tenant_id": tenant_id,
        "content_hash": digest,
        "status": "ready",
        "title": "Note",
        "filename": "note.txt",
        "media_type": "text/plain",
        "source": "upload",
        "source_ref": "",
        "object_key": "",
        "size_bytes": len(data),
        "page_count": None,
        "created_at": None,
    }

    class _Mappings:
        def __init__(self, row: object) -> None:
            self._row = row

        def first(self) -> object:
            return self._row

    class _Result:
        def __init__(self, row: object) -> None:
            self._row = row

        def mappings(self) -> _Mappings:
            return _Mappings(self._row)

    class _Session:
        def __init__(self, _engine: object, expire_on_commit: bool = False) -> None:
            del expire_on_commit

        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *_exc: object) -> bool:
            return False

        def begin(self) -> _Session:
            return self

        async def execute(self, _statement: object, _params: object = None) -> _Result:
            return _Result(loaded)

    monkeypatch.setattr("sqlalchemy.ext.asyncio.AsyncSession", _Session)
    store = SimpleNamespace(
        reloading=False,
        library_documents={},
        durable_engine=create_async_engine("postgresql+asyncpg://ar:ar@127.0.0.1:1/none"),
        originals={},
    )
    actor = Actor(tenant_id, user_id, frozenset())
    view = asyncio.run(
        ingest_bytes(store, actor, data=data, filename="note.txt", media_type="text/plain")
    )
    assert view["deduped"] is True
    assert view["id"] == str(document_id)
    assert store.library_documents[document_id]["object_key"]
    assert store.originals

    store.durable_engine = None
    assert asyncio.run(_load_library_hash(store, tenant_id, digest)) is None
    assert asyncio.run(_load_library_hash(store, tenant_id, "")) is None


def test_adopt_points_the_cache_at_the_existing_document() -> None:
    store = SimpleNamespace(reloading=False, library_documents="not-a-map")
    _adopt_library_rows(store, {})
    _adopt_library_rows(store, {uuid.uuid4(): uuid.uuid4()})

    existing = uuid.uuid4()
    fresh = uuid.uuid4()
    plain: dict[object, object] = {fresh: {"id": fresh, "title": "Again"}}
    store.library_documents = plain
    _adopt_library_rows(store, {fresh: existing})
    assert fresh not in plain
    assert plain[existing]["id"] == existing

    tracked = TrackedDict(store, "library_documents")
    store.library_documents = tracked
    tracked[fresh] = {"id": fresh, "title": "Tracked"}
    tracked.dirty.add(existing)
    _adopt_library_rows(store, {fresh: existing})
    assert fresh not in tracked
    assert existing not in tracked.dirty
    assert tracked[existing]["title"] == "Tracked"


def test_rollback_keeps_a_key_dirtied_again_and_commit_clears_the_baseline() -> None:
    store = SimpleNamespace(reloading=False)
    bucket = TrackedDict(store, "runs")
    key = uuid.uuid4()
    bucket[key] = {"id": key}
    bucket.commit_keys([key])
    assert key not in bucket.baseline
    bucket[key] = {"id": key, "status": "queued"}
    bucket.dirty.add(key)
    bucket.rollback_keys([key])
    assert bucket[key]["status"] == "queued"


def test_missing_embed_is_a_retrieval_failure_not_an_empty_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    collection_id = uuid.uuid4()
    warnings: list[tuple[object, object]] = []

    def _emit(run: object, kind: object, payload: object) -> None:
        del run
        warnings.append((kind, payload))

    store = SimpleNamespace(
        knowledge_collections={
            collection_id: {
                "id": collection_id,
                "tenant_id": tenant_id,
                "slug": "policies",
            }
        },
        _emit=_emit,
    )
    run = {"tenant_id": tenant_id, "user_id": user_id, "prompt_messages": []}
    definition = {"knowledge": {"collections": ["policies"]}, "instructions": "Answer."}

    async def _fail(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise EmbeddingUnconfiguredError()

    monkeypatch.setattr("ar_domain.knowledge.members.retrieve", _fail)
    found = asyncio.run(_retrieve(store, run, definition, "What is the policy?"))
    assert found is not None
    assert found["trace"]["code"] == "embedding_unconfigured"
    assert warnings and warnings[0][0] == "warning"
    _append_system(run, definition, None, found)
    content = str(run["prompt_messages"][0]["content"])
    assert "Knowledge retrieval failed" in content
    assert "Do not invent" in content

    store._emit = "not-callable"
    quiet = asyncio.run(_retrieve(store, {"tenant_id": "nope"}, definition, "again"))
    assert quiet is None
    silent = asyncio.run(_retrieve(store, run, definition, "again"))
    assert silent is not None
    assert silent["trace"]["code"] == "embedding_unconfigured"
    assert len(warnings) == 1


def test_bootstrap_second_user_and_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain import bootstrap as bootstrap_module

    calls: list[dict[str, object]] = []

    async def _ensure(_session: object, **kwargs: object) -> str:
        calls.append(kwargs)
        return str(kwargs["slug"])

    async def _provision(slug: str, email: str) -> None:
        calls.append({"provision": slug, "email": email})

    class _Begin:
        async def __aenter__(self) -> _Begin:
            return self

        async def __aexit__(self, *_exc: object) -> bool:
            return False

    class _Session:
        def __init__(self, _engine: object, expire_on_commit: bool = False) -> None:
            del expire_on_commit

        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *_exc: object) -> bool:
            return False

        def begin(self) -> _Begin:
            return _Begin()

    monkeypatch.setattr(bootstrap_module, "AsyncSession", _Session)
    monkeypatch.setattr(bootstrap_module, "get_engine", lambda _url: object())
    monkeypatch.setattr(bootstrap_module, "owner_database_url", lambda: "postgresql://local/ar")
    monkeypatch.setattr(bootstrap_module, "import_models", lambda: None)
    monkeypatch.setattr(bootstrap_module, "apply_catalogue", lambda _session: asyncio.sleep(0))
    monkeypatch.setattr(bootstrap_module, "ensure_admin", _ensure)
    monkeypatch.setattr(bootstrap_module, "provision_defaults", _provision)

    monkeypatch.delenv("AR_BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("AR_SECOND_EMAIL", raising=False)
    monkeypatch.delenv("AR_SECOND_PASSWORD", raising=False)
    with pytest.raises(SystemExit, match="AR_BOOTSTRAP_ADMIN_EMAIL"):
        asyncio.run(bootstrap_module.bootstrap())
    slug = asyncio.run(
        bootstrap_module.bootstrap(
            slug="acme",
            name="Acme",
            admin_email="admin@acme.test",
            admin_password="secret",  # noqa: S106
            second_email="approver@acme.test",
            second_password="other",  # noqa: S106
            second_role="approver",
        )
    )
    assert slug == "acme"
    assert calls[-1] == {"provision": "acme", "email": "admin@acme.test"}
    assert calls[-2]["email"] == "approver@acme.test"
    assert calls[-2]["role_key"] == "approver"

    with pytest.raises(SystemExit, match="AR_SECOND_PASSWORD"):
        asyncio.run(
            bootstrap_module._second_user(
                _Session(None),
                slug="acme",
                name="Acme",
                email="second@acme.test",
                display_name=None,
                password=None,
                role_key=None,
            )
        )

    monkeypatch.setenv("AR_SECOND_EMAIL", "env@acme.test")
    monkeypatch.setenv("AR_SECOND_PASSWORD", "from-env")
    monkeypatch.setenv("AR_SECOND_ROLE", "member")
    monkeypatch.setenv("AR_SECOND_NAME", "Env User")
    before = len(calls)
    asyncio.run(
        bootstrap_module._second_user(
            _Session(None),
            slug="acme",
            name="Acme",
            email=None,
            display_name=None,
            password=None,
            role_key=None,
        )
    )
    assert calls[before]["email"] == "env@acme.test"
    assert calls[before]["role_key"] == "member"

    asyncio.run(
        bootstrap_module._second_user(
            _Session(None),
            slug="acme",
            name="Acme",
            email="  ",
            display_name=None,
            password=None,
            role_key=None,
        )
    )
    assert len(calls) == before + 1


def test_provision_defaults_writes_builtins_and_closes_the_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ar_domain import bootstrap as bootstrap_module

    disposed: list[bool] = []
    builtins: list[object] = []

    class _Engine:
        async def dispose(self) -> None:
            disposed.append(True)

    class _Store:
        def __init__(self, **_kwargs: object) -> None:
            self.durable_engine = _Engine()

    class _Lifecycle:
        def __init__(self, _store: object) -> None:
            return None

        def ensure_builtins(self, tenant_id: object, owner: object) -> None:
            builtins.append((tenant_id, owner))

    class _Binding:
        def __init__(self) -> None:
            self.tenant_id = uuid.uuid4()
            self.users = {"owner@acme.test": "owner"}

    async def _bind(_store: object, _url: str, *, tenant_slug: str) -> _Binding | None:
        return None if tenant_slug == "missing" else _Binding()

    async def _flush(_store: object) -> None:
        return None

    monkeypatch.setattr("ar_domain.chat.service.ChatService", _Store)
    monkeypatch.setattr("ar_domain.agents.service.AgentLifecycle", _Lifecycle)
    monkeypatch.setattr("ar_domain.durable.bind.bind_store", _bind)
    monkeypatch.setattr("ar_domain.durable.flush.flush_store", _flush)
    monkeypatch.setattr(bootstrap_module, "app_database_url", lambda: "postgresql://local/ar")

    with pytest.raises(SystemExit, match="database"):
        asyncio.run(bootstrap_module.provision_defaults("missing", "owner@acme.test"))
    asyncio.run(bootstrap_module.provision_defaults("acme", "owner@acme.test"))
    assert disposed == [True]
    assert builtins and builtins[0][1] == "owner"


def test_bootstrap_main_runs_the_coroutine(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain import bootstrap as bootstrap_module

    monkeypatch.setattr(bootstrap_module, "bootstrap", lambda: asyncio.sleep(0))
    monkeypatch.setattr(bootstrap_module.asyncio, "run", lambda coro: coro.close())
    bootstrap_module.main()
