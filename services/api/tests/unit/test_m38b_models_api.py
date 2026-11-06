"""What the Models screen needs from the API (M38b-T07c).

The aliases the product uses are listed with whether each is set, one model can be
tested by itself, and what an alias sends by default is a setting.
"""

import uuid

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application
from ar_testing.stand_in import shared

SCRIPT_SET = "m38b-models"


def _client(tenant_id: uuid.UUID | None = None) -> TestClient:
    app = demo_application()
    principal = Principal(
        kind="user",
        id=str(demo_id("admin")),
        tenant_id=tenant_id or demo_id("tenant"),
        permissions=PERMISSION_KEYS,
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Dev Admin",
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    return TestClient(app)


def _provider(client: TestClient, name: str) -> str:
    created = client.post(
        "/api/v1/model-providers",
        json={"name": name, "kind": "openai_compatible", "baseUrl": shared().base_url(SCRIPT_SET)},
    )
    assert created.status_code == 200, created.text
    return str(created.json()["id"])


def _model(client: TestClient, provider_id: str, name: str, kind: str) -> str:
    created = client.post(
        "/api/v1/models",
        json={"providerId": provider_id, "name": name, "upstreamModel": name, "kind": kind},
    )
    assert created.status_code == 200, created.text
    return str(created.json()["id"])


def test_the_aliases_the_product_uses_are_listed_with_whether_each_is_set() -> None:
    client = _client()
    listed = client.get("/api/v1/model-aliases").json()
    standard = {row["alias"]: row for row in listed["standard"]}
    # ``fast`` is named by agent definitions, and nothing is sent to it yet: it is not listed.
    assert list(standard) == ["reasoning", "vision", "embed", "rerank"]
    assert [row["kind"] for row in standard.values()] == ["chat", "chat", "embedding", "rerank"]
    assert [name for name, row in standard.items() if row["required"]] == ["reasoning", "embed"]
    assert standard["vision"]["capability"] == "vision"
    assert standard["reasoning"]["capability"] is None
    # The demo tenant has every one set, by aliases that belong to no tenant.
    assert all(row["set"] and row["platform"] and row["modelName"] for row in standard.values())
    # The tenant points one at a model of its own: its alias wins, and the list says so.
    provider_id = _provider(client, "own")
    model_id = _model(client, provider_id, "own-embed", "embedding")
    made = client.post(
        "/api/v1/model-aliases",
        json={"alias": "embed", "kind": "embedding", "primaryModelId": model_id},
    )
    assert made.status_code == 200, made.text
    embed = {row["alias"]: row for row in client.get("/api/v1/model-aliases").json()["standard"]}[
        "embed"
    ]
    assert (embed["modelId"], embed["modelName"], embed["platform"]) == (
        model_id,
        "own-embed",
        False,
    )
    assert embed["aliasId"] == made.json()["id"]
    # Removing it puts the alias that belongs to no tenant back in force.
    assert client.delete(f"/api/v1/model-aliases/{made.json()['id']}").status_code == 200
    back = {row["alias"]: row for row in client.get("/api/v1/model-aliases").json()["standard"]}
    assert back["embed"]["platform"] is True


def test_one_model_is_tested_by_itself_and_only_by_its_tenant() -> None:
    shared().script(SCRIPT_SET, [{"match": {"contains": "pong"}, "respond": {"text": "pong"}}])
    client = _client()
    provider_id = _provider(client, "probe")
    chat = _model(client, provider_id, "probe-chat", "chat")
    embedding = _model(client, provider_id, "probe-embed", "embedding")
    rerank = _model(client, provider_id, "probe-rerank", "rerank")
    answered = client.post(f"/api/v1/models/{chat}:test")
    assert answered.status_code == 200
    assert (answered.json()["ok"], answered.json()["output"]) == (True, "pong")
    assert answered.json()["modelId"] == "probe-chat"
    vector = client.post(f"/api/v1/models/{embedding}:test").json()
    assert (vector["ok"], vector["output"]) == (True, "Returned a vector of 1024 numbers.")
    scores = client.post(f"/api/v1/models/{rerank}:test").json()
    assert (scores["ok"], scores["output"]) == (True, "Returned 2 scores.")
    assert client.post(f"/api/v1/models/{uuid.uuid4()}:test").status_code == 404


def test_a_model_of_another_tenant_cannot_be_tested() -> None:
    owner = _client()
    provider_id = _provider(owner, "theirs")
    model_id = _model(owner, provider_id, "their-chat", "chat")
    stranger = TestClient(owner.app)
    principal = Principal(
        kind="user",
        id=str(uuid.uuid4()),
        tenant_id=uuid.uuid4(),
        permissions=PERMISSION_KEYS,
        auth_method="bearer",
        email="other@other.example",
        display_name="Other",
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    owner.app.state.resolve_principal = resolve  # type: ignore[attr-defined]
    assert stranger.post(f"/api/v1/models/{model_id}:test").status_code == 404


def test_what_an_alias_sends_by_default_is_a_setting() -> None:
    client = _client()
    provider_id = _provider(client, "params")
    chat = _model(client, provider_id, "params-chat", "chat")
    embedding = _model(client, provider_id, "params-embed", "embedding")
    drafting = client.post(
        "/api/v1/model-aliases", json={"alias": "drafting", "kind": "chat", "primaryModelId": chat}
    ).json()
    assert drafting["defaultParams"] == {"temperature": 0.2}
    vectors = client.post(
        "/api/v1/model-aliases",
        json={"alias": "vectors", "kind": "embedding", "primaryModelId": embedding},
    ).json()
    # A temperature means nothing to an embedding model, so none is sent.
    assert vectors["defaultParams"] == {}
    changed = client.patch(
        f"/api/v1/model-aliases/{drafting['id']}",
        json={"primaryModelId": chat, "defaultParams": {"temperature": 0.7, "top_p": 0.9}},
    )
    assert changed.status_code == 200
    assert changed.json()["defaultParams"] == {"temperature": 0.7, "top_p": 0.9}
    # Leaving the field out keeps what is set.
    kept = client.patch(f"/api/v1/model-aliases/{drafting['id']}", json={"primaryModelId": chat})
    assert kept.json()["defaultParams"] == {"temperature": 0.7, "top_p": 0.9}
    refused = client.patch(
        f"/api/v1/model-aliases/{drafting['id']}",
        json={"primaryModelId": chat, "defaultParams": {"nested": {"a": 1}}},
    )
    assert refused.status_code == 422


def test_what_a_model_can_do_is_set_by_the_tenant() -> None:
    client = _client()
    provider_id = _provider(client, "caps")
    made = client.post(
        "/api/v1/models",
        json={
            "providerId": provider_id,
            "name": "eyes",
            "upstreamModel": "vendor/eyes",
            "kind": "chat",
            "capabilities": ["vision", "tools"],
        },
    )
    assert made.status_code == 200, made.text
    assert made.json()["capabilities"] == ["tools", "vision"]
    cleared = client.patch(f"/api/v1/models/{made.json()['id']}", json={"capabilities": ["tools"]})
    assert cleared.json()["capabilities"] == ["tools"]
    # Leaving the field out keeps what is set.
    kept = client.patch(f"/api/v1/models/{made.json()['id']}", json={"name": "eyes 2"})
    assert kept.json()["capabilities"] == ["tools"]
    unknown = client.patch(
        f"/api/v1/models/{made.json()['id']}", json={"capabilities": ["telepathy"]}
    )
    assert unknown.status_code == 422
    assert "telepathy" in unknown.json()["detail"]
