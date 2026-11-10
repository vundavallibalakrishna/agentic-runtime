"""Batch-two connectors, checked against recorded provider examples.

These calls use an HTTP stand-in. They are not live provider calls.
"""

# ruff: noqa: S105, S106

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, unquote

import httpx
import orjson
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ar_domain.agents.access import Actor
from ar_domain.connectors.book import ConnectorBook
from ar_domain.connectors.catalog import CONNECTORS
from ar_domain.connectors.dispatch import dispatch_connector
from ar_domain.connectors.gcp_auth import service_account_assertion, token_form
from ar_domain.connectors.sigv4 import sign_headers, signature_of
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    import pytest

    from ar_domain.chat.service import ChatService

_BATCH = {
    "servicenow",
    "salesforce",
    "zendesk",
    "hubspot",
    "okta",
    "entra",
    "aws",
    "azure",
    "gcp",
}
_S3_GET = "f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
_S3_PUT = "98ad721746da40c64f1a55b78f14c238d841ea1380cd77a1b5971af0ece108bd"
_WHEN = datetime(2013, 5, 24, tzinfo=UTC)
_AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def _actor() -> Actor:
    return Actor(uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS)


def _install(store: ChatService, actor: Actor, slug: str, **extra: object) -> dict[str, object]:
    body: dict[str, object] = {
        "connection_name": slug,
        "secret": extra.pop("secret", "secret-value"),
        "username": extra.pop("username", "ada@example.com"),
        "client_id": extra.pop("client_id", "client"),
        "config": {
            "baseUrl": "https://example.com",
            "tenantId": "contoso",
            "subscriptionId": "sub",
            "projectId": "demo",
            "region": "us-east-1",
            **(extra.pop("config", {}) if isinstance(extra.get("config"), dict) else {}),
        },
    }
    body.update(extra)
    return ConnectorBook(store).install(actor, slug, body)


def _args(actor: Actor, **values: object) -> dict[str, object]:
    return {"_tenant_id": actor.tenant_id, "_user_id": actor.user_id, **values}


def test_published_s3_signatures() -> None:
    get = sign_headers(
        "GET",
        "https://examplebucket.s3.amazonaws.com/test.txt",
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key=_AWS_SECRET,
        region="us-east-1",
        service="s3",
        now=_WHEN,
        extra={"range": "bytes=0-9"},
    )
    assert signature_of(get) == _S3_GET
    put = sign_headers(
        "PUT",
        "https://examplebucket.s3.amazonaws.com/test$file.text",
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key=_AWS_SECRET,
        region="us-east-1",
        service="s3",
        now=_WHEN,
        body=b"Welcome to Amazon S3.",
        extra={
            "date": "Fri, 24 May 2013 00:00:00 GMT",
            "x-amz-storage-class": "REDUCED_REDUNDANCY",
        },
    )
    assert signature_of(put) == _S3_PUT
    assert _AWS_SECRET not in put["authorization"]


def test_guides_match_the_catalogue() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[4] / "docs/11-connectors"
    for connector in CONNECTORS:
        if connector.slug not in _BATCH:
            continue
        text = (root / f"{connector.slug}.md").read_text()
        assert "Not live-tested" in text
        assert connector.registration_url in text
        for tool in connector.tools:
            assert f"`{tool.name}`" in text


def test_batch_is_labelled_and_writes_wait() -> None:
    slugs = {item.slug for item in CONNECTORS}
    assert _BATCH <= slugs
    for connector in CONNECTORS:
        if connector.slug not in _BATCH:
            continue
        assert connector.verification == "not_live"
        assert "Not live-tested" in connector.verification_note
        assert connector.registration_url.startswith("https://")
        assert connector.steps
        assert connector.scopes
        for tool in connector.tools:
            assert tool.risk in {"R0", "W2"}
    writes = {
        "servicenow_create_incident",
        "servicenow_update_change",
        "salesforce_create_record",
        "salesforce_update_record",
        "zendesk_create_ticket",
        "zendesk_add_comment",
        "hubspot_create_contact",
        "hubspot_update_contact",
        "okta_deactivate_user",
    }
    for connector in CONNECTORS:
        for tool in connector.tools:
            if tool.name in writes:
                assert tool.risk == "W2"


def test_servicenow_example_pagination_and_errors() -> None:
    store = demo_store()
    actor = _actor()
    detail = _install(store, actor, "servicenow", kind="basic")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path.endswith("/incident/abc"):
            return httpx.Response(
                200,
                json={
                    "result": {
                        "sys_id": "abc",
                        "number": "INC0000001",
                        "short_description": "Can't read email",
                    }
                },
            )
        if "sysparm_offset=1" in str(request.url):
            return httpx.Response(200, json={"result": [{"number": "INC0000002"}]})
        if "sysparm_offset=" in str(request.url):
            return httpx.Response(200, json={"result": []})
        if request.url.path.endswith("/missing"):
            return httpx.Response(404, json={"error": {"message": "not found"}})
        if request.method == "POST":
            return httpx.Response(429, json={}, headers={"Retry-After": "9"})
        return httpx.Response(200, json={"result": [{"number": "INC0000001"}]})

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    read = dispatch_connector(store, "servicenow_get_incident", _args(actor, sys_id="abc"))
    assert read["is_error"] is False
    assert read["structured"]["result"]["number"] == "INC0000001"
    listed = dispatch_connector(
        store,
        "servicenow_query_table",
        _args(actor, table="incident", sysparm_query="active=true", sysparm_limit=1),
    )
    assert [item["number"] for item in listed["structured"]["items"]][:2] == [
        "INC0000001",
        "INC0000002",
    ]
    assert listed["structured"]["pages"] >= 2
    missing = dispatch_connector(store, "servicenow_get_incident", _args(actor, sys_id="missing"))
    assert "404" in str(missing["text"])
    limited = dispatch_connector(
        store, "servicenow_create_incident", _args(actor, short_description="disk")
    )
    assert "429" in str(limited["text"])
    assert "9" in str(limited["text"])
    install_id = uuid.UUID(str(detail["install"]["id"]))
    ConnectorBook(store).update(
        actor, install_id, {"disabled_tools": ["servicenow_create_incident"]}
    )
    blocked = dispatch_connector(
        store, "servicenow_create_incident", _args(actor, short_description="disk")
    )
    assert blocked["code"] == "tool_disabled"
    assert seen


def test_salesforce_zendesk_and_hubspot_examples() -> None:
    store = demo_store()
    actor = _actor()
    _install(store, actor, "salesforce", kind="bearer")
    _install(store, actor, "zendesk", kind="basic", username="ada@example.com/token")
    _install(store, actor, "hubspot", kind="bearer")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/query/01g"):
            return httpx.Response(
                200,
                json={"records": [{"Name": "Second", "Id": "002"}], "done": True},
            )
        if path.endswith("/query"):
            return httpx.Response(
                200,
                json={
                    "totalSize": 2,
                    "done": False,
                    "records": [
                        {
                            "Name": "Edge Communications",
                            "Id": "001xx000003DGb0AAG",
                        }
                    ],
                    "nextRecordsUrl": "/services/data/v59.0/query/01g",
                },
            )
        if "page=2" in str(request.url):
            return httpx.Response(200, json={"results": [{"id": 35437}], "next_page": None})
        if path.endswith("/tickets/35436.json") and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "ticket": {
                        "id": 35436,
                        "subject": "Help, my printer is on fire!",
                        "status": "open",
                    }
                },
            )
        if path.endswith("/search.json"):
            return httpx.Response(
                200,
                json={
                    "results": [{"id": 35436, "result_type": "ticket"}],
                    "next_page": "https://example.com/api/v2/search.json?page=2",
                    "count": 1,
                },
            )
        if path.endswith("/contacts/search"):
            body = orjson.loads(request.content)
            if body.get("after") == "cursor-2":
                return httpx.Response(200, json={"results": [{"id": "2"}]})
            return httpx.Response(
                200,
                json={
                    "results": [{"id": "1", "properties": {"email": "jsmith@example.com"}}],
                    "paging": {"next": {"after": "cursor-2"}},
                },
            )
        if path.endswith("/contacts/1"):
            return httpx.Response(
                200,
                json={
                    "id": "1",
                    "properties": {"email": "jsmith@example.com", "firstname": "John"},
                },
            )
        return httpx.Response(403, json={"message": "no"})

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    queried = dispatch_connector(
        store, "salesforce_query", _args(actor, q="SELECT Name FROM Account")
    )
    names = [item["Name"] for item in queried["structured"]["items"]]
    assert names == ["Edge Communications", "Second"]
    ticket = dispatch_connector(store, "zendesk_read_ticket", _args(actor, ticket_id="35436"))
    assert ticket["structured"]["ticket"]["subject"] == "Help, my printer is on fire!"
    found = dispatch_connector(
        store, "zendesk_search_tickets", _args(actor, query="type:ticket printer")
    )
    assert found["structured"]["pages"] == 2
    contacts = dispatch_connector(store, "hubspot_search_contacts", _args(actor, query="jsmith"))
    assert [item["id"] for item in contacts["structured"]["items"]] == ["1", "2"]
    one = dispatch_connector(store, "hubspot_read_contact", _args(actor, contact_id="1"))
    assert one["structured"]["properties"]["firstname"] == "John"
    denied = dispatch_connector(store, "hubspot_read_company", _args(actor, company_id="9"))
    assert "403" in str(denied["text"])


def test_okta_sends_ssws_and_entra_follows_the_next_link() -> None:
    store = demo_store()
    actor = _actor()
    _install(store, actor, "okta", kind="bearer", secret="okta-token")
    _install(store, actor, "entra", kind="oauth_client_credentials", secret="entra-secret")
    headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        headers.append(request.headers.get("authorization", ""))
        if request.url.host == "login.microsoftonline.com":
            return httpx.Response(200, json={"access_token": "graph-token", "expires_in": 3600})
        if request.url.path == "/api/v1/users" and "after" not in str(request.url):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "00u1abc",
                        "status": "ACTIVE",
                        "profile": {"login": "jsmith@example.com"},
                    }
                ],
                headers={"Link": '<https://example.com/api/v1/users?after=cursor>; rel="next"'},
            )
        if "after=cursor" in str(request.url):
            return httpx.Response(200, json=[{"id": "00u1abd", "status": "ACTIVE"}])
        if "skiptoken" in str(request.url):
            return httpx.Response(200, json={"value": [{"displayName": "Alex"}]})
        if request.url.path == "/users":
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "87d349ed-44d7-43e1-9a83-5f2406dee5bd",
                            "displayName": "Adele Vance",
                        }
                    ],
                    "@odata.nextLink": "https://example.com/users?$skiptoken=page2",
                },
            )
        return httpx.Response(401, json={})

    transport = httpx.MockTransport(handler)
    store.connector_transport = transport  # type: ignore[attr-defined]
    for row in store.service_connections.values():
        if str(row.get("name")) == "entra":
            row["_token_transport"] = transport
    users = dispatch_connector(store, "okta_list_users", _args(actor))
    assert users["structured"]["pages"] == 2
    assert headers[0] == "SSWS okta-token"
    people = dispatch_connector(store, "entra_list_users", _args(actor))
    names = [item["displayName"] for item in people["structured"]["items"]]
    assert names == ["Adele Vance", "Alex"]
    rejected = dispatch_connector(store, "okta_read_user", _args(actor, user_id="missing"))
    assert "401" in str(rejected["text"])


def test_azure_token_matches_the_published_form_and_is_cached() -> None:
    store = demo_store()
    actor = _actor()
    _install(store, actor, "azure", kind="oauth_client_credentials", secret="azure-secret")
    posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            posts.append(unquote(request.content.decode()))
            return httpx.Response(200, json={"access_token": "arm-token", "expires_in": 3600})
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "name": "vm1",
                        "type": "Microsoft.Compute/virtualMachines",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    store.connector_transport = transport  # type: ignore[attr-defined]
    for row in store.service_connections.values():
        row["_token_transport"] = transport
    first = dispatch_connector(store, "azure_list_resources", _args(actor))
    second = dispatch_connector(store, "azure_list_resources", _args(actor))
    assert first["structured"]["items"][0]["name"] == "vm1"
    assert second["is_error"] is False
    assert len(posts) == 1
    form = parse_qs(posts[0])
    assert form["grant_type"] == ["client_credentials"]
    assert form["scope"] == ["https://management.azure.com/.default"]
    assert form["client_id"] == ["client"]
    assert "azure-secret" not in str(first)


def test_google_jwt_matches_the_documented_claims() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    info = {
        "client_email": "worker@demo.iam.gserviceaccount.com",
        "private_key": private,
        "private_key_id": "key-1",
    }
    now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    raw = service_account_assertion(
        info, ("https://www.googleapis.com/auth/cloud-platform.read-only",), now
    )
    header, claims, signature = raw.split(".")
    decoded_header = orjson.loads(_pad(header))
    decoded_claims = orjson.loads(_pad(claims))
    assert decoded_header["alg"] == "RS256"
    assert decoded_header["kid"] == "key-1"
    assert decoded_claims["iss"] == info["client_email"]
    assert decoded_claims["aud"] == "https://oauth2.googleapis.com/token"
    assert decoded_claims["scope"] == "https://www.googleapis.com/auth/cloud-platform.read-only"
    assert decoded_claims["exp"] == decoded_claims["iat"] + 3600
    signing = f"{header}.{claims}".encode()
    key.public_key().verify(_pad_bytes(signature), signing, padding.PKCS1v15(), hashes.SHA256())
    form = token_form(raw)
    assert form["grant_type"] == "urn:ietf:params:oauth:grant-type:jwt-bearer"


def test_gcp_exchanges_a_jwt_once_and_lists_the_documented_project() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    secret = orjson.dumps(
        {"client_email": "worker@demo.iam.gserviceaccount.com", "private_key": private}
    ).decode()
    store = demo_store()
    actor = _actor()
    _install(store, actor, "gcp", kind="api_key", secret=secret)
    posts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal posts
        if request.url.host == "oauth2.googleapis.com":
            posts += 1
            form = unquote(request.content.decode())
            assert "urn:ietf:params:oauth:grant-type:jwt-bearer" in form
            return httpx.Response(200, json={"access_token": "ya29.demo", "expires_in": 3600})
        if request.url.path == "/v1/projects":
            return httpx.Response(
                200,
                json={"projects": [{"projectId": "example-project", "name": "Example"}]},
            )
        return httpx.Response(200, json={"items": []})

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    listed = dispatch_connector(store, "gcp_list_projects", _args(actor))
    again = dispatch_connector(store, "gcp_list_projects", _args(actor))
    assert listed["structured"]["items"][0]["projectId"] == "example-project"
    assert again["is_error"] is False
    assert posts == 1
    assert private not in str(listed)


def test_aws_reads_recorded_xml_and_caches_a_role() -> None:
    store = demo_store()
    actor = _actor()
    _install(
        store,
        actor,
        "aws",
        kind="basic",
        username="AKIDEXAMPLE",
        secret="secret-key",
        config={"region": "us-east-1", "roleArn": "arn:aws:iam::123:role/ReadOnly"},
    )
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers.get("authorization", ""))
        body = request.content.decode()
        if "AssumeRole" in body:
            return httpx.Response(
                200,
                content=(
                    b"<AssumeRoleResponse><AssumeRoleResult><Credentials>"
                    b"<AccessKeyId>ASIAFAKE</AccessKeyId>"
                    b"<SecretAccessKey>temp-secret</SecretAccessKey>"
                    b"<SessionToken>session-token</SessionToken>"
                    b"<Expiration>2099-01-01T00:00:00Z</Expiration>"
                    b"</Credentials></AssumeRoleResult></AssumeRoleResponse>"
                ),
            )
        if "DescribeInstances" in body:
            return httpx.Response(
                200,
                content=(
                    b"<DescribeInstancesResponse><reservationSet><item><instancesSet><item>"
                    b"<instanceId>i-123</instanceId>"
                    b"<instanceState><name>running</name></instanceState>"
                    b"</item></instancesSet></item></reservationSet></DescribeInstancesResponse>"
                ),
            )
        if str(request.url.host).startswith("iam."):
            return httpx.Response(
                200,
                content=(
                    b"<ListUsersResponse><ListUsersResult><Users><member>"
                    b"<UserName>ada</UserName></member></Users>"
                    b"<IsTruncated>false</IsTruncated></ListUsersResult></ListUsersResponse>"
                ),
            )
        return httpx.Response(
            400,
            content=b"<Error><Code>RequestLimitExceeded</Code></Error>",
            headers={"Retry-After": "7"},
        )

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    listed = dispatch_connector(store, "aws_list_instances", _args(actor))
    again = dispatch_connector(store, "aws_list_instances", _args(actor))
    users = dispatch_connector(store, "aws_list_iam_users", _args(actor))
    limited = dispatch_connector(store, "aws_list_buckets", _args(actor))
    assert listed["structured"]["instances"][0] == {"instanceId": "i-123", "state": "running"}
    assert again["structured"]["instances"][0]["instanceId"] == "i-123"
    assert users["structured"]["users"][0]["userName"] == "ada"
    assert "429" in str(limited["text"])
    assert "7" in str(limited["text"])
    assert sum("AssumeRole" in item or "ASIAFAKE" in item for item in calls) >= 1
    assume_calls = [item for item in calls if "AKIDEXAMPLE" in item]
    assert len(assume_calls) == 1
    assert "secret-key" not in " ".join(calls)
    assert "temp-secret" not in " ".join(calls)


def test_shared_rate_limit_counts_across_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    # The shared key includes the current minute. A slow suite can cross that
    # boundary and reset the counter, so the next call is not limited.
    monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)

    class _Valkey:
        def __init__(self) -> None:
            self.values: dict[str, int] = {}

        def incr(self, key: str) -> int:
            self.values[key] = self.values.get(key, 0) + 1
            return self.values[key]

        def expire(self, key: str, ttl: int) -> bool:
            del key, ttl
            return True

    client = _Valkey()
    first = demo_store()
    second = demo_store()
    first.valkey_client = client  # type: ignore[attr-defined]
    second.valkey_client = client  # type: ignore[attr-defined]
    actor = _actor()
    _install(first, actor, "okta", kind="bearer")
    _install(second, actor, "okta", kind="bearer")
    first.connector_transport = httpx.MockTransport(  # type: ignore[attr-defined]
        lambda _request: httpx.Response(200, json=[])
    )
    second.connector_transport = first.connector_transport  # type: ignore[attr-defined]
    arguments = _args(actor)
    for _ in range(30):
        dispatch_connector(first, "okta_list_users", arguments)
    blocked = dispatch_connector(second, "okta_list_users", arguments)
    assert blocked["code"] == "rate_limited"
    assert "shared limit" in str(blocked["text"])


def test_token_cache_is_sealed_and_shared() -> None:
    from ar_common.time import utcnow
    from ar_domain.connectors.tokens import cached_token, expiry_stamp, remember_token

    class _Valkey:
        def __init__(self) -> None:
            self.data: dict[str, object] = {}
            self.fail = False

        def get(self, key: str) -> object:
            if self.fail:
                raise RuntimeError("down")
            return self.data.get(key)

        def set(self, key: str, value: str, ex: int) -> None:
            del ex
            if self.fail:
                raise RuntimeError("down")
            self.data[key] = value

    store = demo_store()
    actor = _actor()
    _install(store, actor, "azure", kind="oauth_client_credentials")
    row = next(iter(store.service_connections.values()))
    remember_token(store, row, "", 10)
    remember_token(store, row, "arm-token", 10)
    assert cached_token(store, row) == "arm-token"
    row["expires_at"] = "2000-01-01T00:00:00+00:00"
    assert cached_token(store, row) == ""
    client = _Valkey()
    store.valkey_client = client  # type: ignore[attr-defined]
    row["expires_at"] = ""
    remember_token(store, row, "shared-token", 3600)
    fresh = {"id": row["id"], "access_token": b"", "expires_at": "2000-01-01T00:00:00+00:00"}
    assert cached_token(store, fresh) == "shared-token"
    key = f"ar:cloud-token:{row['id']}"
    client.data[key] = "2099-01-01T00:00:00+00:00\nnot-hex"
    stale = {"id": row["id"], "access_token": b"", "expires_at": "2000-01-01T00:00:00+00:00"}
    assert cached_token(store, stale) == ""
    client.data[key] = "not-a-date\nab"
    assert cached_token(store, stale) == ""
    client.data[key] = "2099-01-01T00:00:00\nab"
    assert cached_token(store, stale) == ""
    client.data[key] = b"2099-01-01T00:00:00+00:00\nab"
    assert cached_token(store, stale) == ""
    client.fail = True
    assert cached_token(store, stale) == ""
    remember_token(store, row, "still-local", 60)
    assert expiry_stamp(1) > utcnow()


def test_aws_reads_buckets_policies_events_and_errors() -> None:
    from ar_domain.connectors.aws_api import probe_aws, run_aws
    from ar_domain.connectors.catalog import tool_by_name

    store = demo_store()
    actor = _actor()
    _install(
        store,
        actor,
        "aws",
        kind="basic",
        username="AKIDEXAMPLE",
        secret="secret-key\nsession-token",
        config={"region": "us-east-1"},
    )
    install = next(iter(store.connector_installs.values()))

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        host = str(request.url.host)
        if "GetCallerIdentity" in body:
            return httpx.Response(
                200,
                content=b"<GetCallerIdentityResult><Account>123</Account></GetCallerIdentityResult>",
            )
        if host.startswith("s3."):
            return httpx.Response(
                200,
                content=b"<ListAllMyBucketsResult><Buckets><Bucket><Name>proof</Name></Bucket></Buckets></ListAllMyBucketsResult>",
            )
        if "ListPolicies" in str(request.url):
            if "Marker" in str(request.url):
                return httpx.Response(
                    200,
                    content=b"<ListPoliciesResult><Policies><member><PolicyName>Local</PolicyName><Arn>arn:aws:iam::1:policy/Local</Arn></member></Policies><IsTruncated>false</IsTruncated></ListPoliciesResult>",
                )
            return httpx.Response(
                200,
                content=b"<ListPoliciesResult><Policies><member><PolicyName>Local</PolicyName><Arn>arn:aws:iam::1:policy/Local</Arn></member></Policies><IsTruncated>true</IsTruncated><Marker>next</Marker></ListPoliciesResult>",
            )
        if "LookupEvents" in request.headers.get("x-amz-target", ""):
            if b"NextToken" in request.content:
                return httpx.Response(
                    200, json={"Events": [{"EventId": "2", "EventName": "DescribeInstances"}]}
                )
            return httpx.Response(
                200,
                json={
                    "Events": [{"EventId": "1", "EventName": "ConsoleLogin"}],
                    "NextToken": "more",
                },
            )
        if "DescribeInstances" in body and "i-missing" in body:
            return httpx.Response(403, content=b"<Error><Code>AccessDenied</Code></Error>")
        if "DescribeInstances" in body:
            return httpx.Response(400, content=b"<Error><Code>SignatureDoesNotMatch</Code></Error>")
        return httpx.Response(401, json={"Code": "InvalidClientTokenId"})

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    buckets = dispatch_connector(store, "aws_list_buckets", _args(actor))
    policies = dispatch_connector(store, "aws_list_iam_policies", _args(actor))
    events = dispatch_connector(store, "aws_list_cloudtrail_events", _args(actor))
    denied = dispatch_connector(
        store, "aws_describe_instance", _args(actor, instance_id="i-missing")
    )
    signed = dispatch_connector(store, "aws_list_instances", _args(actor))
    assert buckets["structured"]["buckets"] == ["proof"]
    assert policies["structured"]["policies"][0]["policyName"] == "Local"
    assert policies["structured"]["pages"] == 2
    assert [item["eventName"] for item in events["structured"]["events"]] == [
        "ConsoleLogin",
        "DescribeInstances",
    ]
    assert "403" in str(denied["text"])
    assert "signature" in str(signed["text"]).lower()
    found = tool_by_name("aws_describe_instance")
    assert found is not None
    missing = run_aws(store, found[1], {}, install, "AKIDEXAMPLE", "secret-key")
    assert missing["code"] == "validation_failed"
    empty = run_aws(store, found[1], {"instance_id": "i-1"}, install, "", "")
    assert empty["code"] == "credential_required"
    probed = probe_aws(store, install, "AKIDEXAMPLE", "secret-key")
    assert probed["ok"] is True
    assert probed["account"] == "123"


def test_recorded_bodies_and_a_failed_google_exchange() -> None:
    from ar_domain.connectors.shape_batch import batch_body, is_unset

    assert batch_body("salesforce_create_record", {"fields": {"Name": "Edge"}}) == {"Name": "Edge"}
    assert batch_body("salesforce_create_record", {"fields": "not-json"}) == {}
    assert batch_body("salesforce_update_record", {"fields": ["nope"]}) == {}
    assert is_unset(batch_body("not_a_tool", {}))
    store = demo_store()
    actor = _actor()
    _install(store, actor, "gcp", kind="api_key", secret="not-json")
    failed = dispatch_connector(store, "gcp_list_projects", _args(actor))
    assert failed["code"] == "credential_required"

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    secret = orjson.dumps(
        {"client_email": "worker@demo.iam.gserviceaccount.com", "private_key": private}
    ).decode()
    store = demo_store()
    _install(store, actor, "gcp", kind="api_key", secret=secret)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    refused = dispatch_connector(store, "gcp_list_projects", _args(actor))
    assert refused["code"] == "credential_required"


def test_aws_refuses_metadata_and_a_failed_role() -> None:
    from ar_domain.connectors.aws_api import probe_aws, run_aws
    from ar_domain.connectors.catalog import ToolDef

    store = demo_store()
    actor = _actor()
    _install(
        store,
        actor,
        "aws",
        kind="basic",
        username="AKIDEXAMPLE",
        secret="secret-key",
        config={
            "region": "us-east-1",
            "roleArn": "arn:aws:iam::123:role/ReadOnly",
            "externalId": "outside",
            "endpoint": "http://169.254.169.254",
        },
    )
    blocked = dispatch_connector(store, "aws_list_buckets", _args(actor))
    assert blocked["code"] == "upstream_error"
    assert "169.254.169.254" in str(blocked["text"])
    install = next(iter(store.connector_installs.values()))
    install["config"] = {"region": "us-east-1", "roleArn": "arn:aws:iam::123:role/ReadOnly"}

    def handler(request: httpx.Request) -> httpx.Response:
        if b"AssumeRole" in request.content:
            return httpx.Response(403, content=b"<Error><Code>AccessDenied</Code></Error>")
        return httpx.Response(200, content=b"<GetCallerIdentityResult></GetCallerIdentityResult>")

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    failed = dispatch_connector(store, "aws_list_instances", _args(actor))
    assert failed["code"] == "upstream_error"
    quiet = probe_aws(store, install, "AKIDEXAMPLE", "secret-key")
    assert quiet["ok"] is False
    install["config"] = {"region": "us-east-1"}
    unknown = ToolDef("aws_other", "Other", "Other action.", "R0", "GET", "", kind="aws")
    missed = run_aws(store, unknown, {}, install, "AKIDEXAMPLE", "secret-key")
    assert missed["code"] == "unknown_tool"
    secret = orjson.dumps({"client_email": "worker@demo.iam.gserviceaccount.com"}).decode()
    gcp = demo_store()
    _install(gcp, actor, "gcp", kind="api_key", secret=secret)
    assert (
        dispatch_connector(gcp, "gcp_list_projects", _args(actor))["code"] == "credential_required"
    )


def test_valkey_rate_limit_falls_back_when_the_client_errors() -> None:
    class _Down:
        def incr(self, key: str) -> int:
            del key
            raise RuntimeError("down")

    store = demo_store()
    actor = _actor()
    _install(store, actor, "okta", kind="bearer")
    store.valkey_client = _Down()  # type: ignore[attr-defined]
    store.connector_transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=[]))  # type: ignore[attr-defined]
    result = dispatch_connector(store, "okta_list_users", _args(actor))
    assert result["is_error"] is False


def _pad(segment: str) -> bytes:
    return _pad_bytes(segment)


def _pad_bytes(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(padded)
