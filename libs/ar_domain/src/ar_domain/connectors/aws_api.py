"""Read-only AWS calls signed with Signature Version 4.

A connection holds an access key (username) and a secret key. A second line
in the secret is an optional session token. When the install names a role,
STS AssumeRole supplies temporary keys that are cached on the connection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlencode
from xml.etree import ElementTree

import httpx
import orjson

from ar_common.offload import blocking
from ar_domain.connectors.http import explain_status
from ar_domain.connectors.sigv4 import sign_headers
from ar_domain.connectors.tokens import cached_token, remember_token
from ar_domain.tools.http_tools import guard_public

if TYPE_CHECKING:
    from ar_domain.connectors.catalog import ToolDef

_PAGE_CAP = 3
_ITEM_CAP = 50


def run_aws(  # noqa: PLR0917
    store: Any,
    tool: ToolDef,
    arguments: dict[str, object],
    install: dict[str, object],
    username: str,
    secret: str,
) -> dict[str, object]:
    config = _config(install)
    creds = _credentials(store, install, username, secret, config)
    if isinstance(creds, dict):
        return creds
    access_key, secret_key, session_token = creds
    region = config.get("region") or "us-east-1"
    endpoint = config.get("endpoint", "").rstrip("/")
    name = tool.name
    if name.endswith("list_instances") or name.endswith("describe_instance"):
        return _ec2(store, name, arguments, access_key, secret_key, session_token, region, endpoint)
    if name.endswith("list_buckets"):
        return _s3(store, access_key, secret_key, session_token, region, endpoint)
    if name.endswith("list_iam_users") or name.endswith("list_iam_policies"):
        return _iam(store, name, access_key, secret_key, session_token, endpoint)
    if name.endswith("list_cloudtrail_events"):
        return _trail(store, access_key, secret_key, session_token, region, endpoint)
    return _fail("unknown_tool", f"Unknown AWS action {name}.")


def probe_aws(
    store: Any, install: dict[str, object], username: str, secret: str
) -> dict[str, object]:
    config = _config(install)
    creds = _credentials(store, install, username, secret, config)
    if isinstance(creds, dict):
        return {"ok": False, "status": 0, "error": str(creds.get("text") or "credentials rejected")}
    access_key, secret_key, session_token = creds
    region = config.get("region") or "us-east-1"
    endpoint = config.get("endpoint", "").rstrip("/")
    url = _base(endpoint, f"https://sts.{region}.amazonaws.com/")
    body = _form({"Action": "GetCallerIdentity", "Version": "2011-06-15"})
    status, payload, headers = _signed(
        store,
        "POST",
        url,
        body,
        access_key,
        secret_key,
        session_token,
        region,
        "sts",
        {"content-type": "application/x-www-form-urlencoded"},
    )
    if isinstance(payload, dict) and payload.get("error"):
        return {"ok": False, "status": status, "error": str(payload["error"])}
    if status >= 400:
        return {"ok": False, "status": status, "error": _aws_error(status, payload, headers)}
    account = _xml_value(payload, "Account")
    if not account:
        return {"ok": False, "status": status, "error": "AWS did not return an account id."}
    return {"ok": True, "status": status, "error": None, "account": account}


def _credentials(
    store: Any,
    install: dict[str, object],
    username: str,
    secret: str,
    config: dict[str, str],
) -> tuple[str, str, str] | dict[str, object]:
    access_key, secret_key, session_token = _split(username, secret)
    if not access_key or not secret_key:
        return _fail("credential_required", "Set the access key id and the secret access key.")
    role = config.get("roleArn", "")
    if not role:
        return access_key, secret_key, session_token
    row = _row(store, install)
    if row is not None:
        cached = _cached_role(store, row)
        if cached is not None:
            return cached
    assumed = _assume(
        store,
        access_key,
        secret_key,
        session_token,
        role,
        config.get("externalId", ""),
        config.get("region") or "us-east-1",
        config.get("endpoint", "").rstrip("/"),
    )
    if isinstance(assumed, dict):
        return assumed
    if row is not None:
        sealed = {
            "accessKeyId": assumed[0],
            "secretAccessKey": assumed[1],
            "sessionToken": assumed[2],
        }
        remember_token(store, row, orjson.dumps(sealed).decode(), _seconds_until(assumed[3]))
    return assumed[0], assumed[1], assumed[2]


def _assume(  # noqa: PLR0917
    store: Any,
    access_key: str,
    secret_key: str,
    session_token: str,
    role: str,
    external_id: str,
    region: str,
    endpoint: str,
) -> tuple[str, str, str, str] | dict[str, object]:
    fields = {
        "Action": "AssumeRole",
        "Version": "2011-06-15",
        "RoleArn": role,
        "RoleSessionName": "agentic-runtime",
    }
    if external_id:
        fields["ExternalId"] = external_id
    url = _base(endpoint, f"https://sts.{region}.amazonaws.com/")
    body = _form(fields)
    status, payload, headers = _signed(
        store,
        "POST",
        url,
        body,
        access_key,
        secret_key,
        session_token,
        region,
        "sts",
        {"content-type": "application/x-www-form-urlencoded"},
    )
    if status >= 400 or isinstance(payload, dict):
        return _fail("upstream_error", _aws_error(status, payload, headers))
    key_id = _xml_value(payload, "AccessKeyId")
    key_secret = _xml_value(payload, "SecretAccessKey")
    token = _xml_value(payload, "SessionToken")
    expiration = _xml_value(payload, "Expiration")
    if not key_id or not key_secret or not token:
        return _fail("upstream_error", "AWS AssumeRole did not return temporary credentials.")
    return key_id, key_secret, token, expiration


def _ec2(  # noqa: PLR0917
    store: Any,
    name: str,
    arguments: dict[str, object],
    access_key: str,
    secret_key: str,
    session_token: str,
    region: str,
    endpoint: str,
) -> dict[str, object]:
    items: list[dict[str, str]] = []
    token = ""
    pages = 0
    while pages < _PAGE_CAP:
        fields = {"Action": "DescribeInstances", "Version": "2016-11-15"}
        if name.endswith("describe_instance"):
            instance = str(arguments.get("instance_id") or "")
            if not instance:
                return _fail("validation_failed", "instance_id is required")
            fields["Filter.1.Name"] = "instance-id"
            fields["Filter.1.Value.1"] = instance
        if token:
            fields["NextToken"] = token
        status, payload, headers = _signed(
            store,
            "POST",
            _base(endpoint, f"https://ec2.{region}.amazonaws.com/"),
            _form(fields),
            access_key,
            secret_key,
            session_token,
            region,
            "ec2",
            {"content-type": "application/x-www-form-urlencoded"},
        )
        if status >= 400:
            return _fail("upstream_error", _aws_error(status, payload, headers))
        found = _instances(payload)
        items.extend(found)
        pages += 1
        token = _xml_value(payload, "nextToken") if not isinstance(payload, dict) else ""
        if not token or len(items) >= _ITEM_CAP:
            break
    shown = items[:_ITEM_CAP]
    return _ok({"instances": shown, "pages": pages})


def _s3(  # noqa: PLR0917
    store: Any,
    access_key: str,
    secret_key: str,
    session_token: str,
    region: str,
    endpoint: str,
) -> dict[str, object]:
    url = _base(endpoint, f"https://s3.{region}.amazonaws.com/")
    status, payload, headers = _signed(
        store, "GET", url, b"", access_key, secret_key, session_token, region, "s3", {}
    )
    if status >= 400:
        return _fail("upstream_error", _aws_error(status, payload, headers))
    names = _children(payload, "Bucket", "Name")
    return _ok({"buckets": names[:_ITEM_CAP], "pages": 1})


def _iam(  # noqa: PLR0917
    store: Any,
    name: str,
    access_key: str,
    secret_key: str,
    session_token: str,
    endpoint: str,
) -> dict[str, object]:
    action = "ListPolicies" if name.endswith("policies") else "ListUsers"
    items: list[dict[str, str]] = []
    marker = ""
    pages = 0
    while pages < _PAGE_CAP:
        fields = {"Action": action, "Version": "2010-05-08", "MaxItems": "50"}
        if action == "ListPolicies":
            fields["Scope"] = "Local"
        if marker:
            fields["Marker"] = marker
        query = urlencode(sorted(fields.items()), quote_via=quote)
        url = _base(endpoint, "https://iam.amazonaws.com/")
        joiner = "&" if "?" in url else "?"
        status, payload, headers = _signed(
            store,
            "GET",
            f"{url}{joiner}{query}",
            b"",
            access_key,
            secret_key,
            session_token,
            "us-east-1",
            "iam",
            {},
        )
        if status >= 400:
            return _fail("upstream_error", _aws_error(status, payload, headers))
        if action == "ListUsers":
            items.extend({"userName": item} for item in _children(payload, "member", "UserName"))
        else:
            items.extend(_policies(payload))
        pages += 1
        truncated = _xml_value(payload, "IsTruncated").lower() == "true"
        marker = _xml_value(payload, "Marker") if truncated else ""
        if not marker or len(items) >= _ITEM_CAP:
            break
    key = "policies" if action == "ListPolicies" else "users"
    return _ok({key: items[:_ITEM_CAP], "pages": pages})


def _trail(  # noqa: PLR0917
    store: Any,
    access_key: str,
    secret_key: str,
    session_token: str,
    region: str,
    endpoint: str,
) -> dict[str, object]:
    items: list[dict[str, str]] = []
    token = ""
    pages = 0
    while pages < _PAGE_CAP:
        body: dict[str, object] = {"MaxResults": 50}
        if token:
            body["NextToken"] = token
        raw = orjson.dumps(body)
        status, payload, headers = _signed(
            store,
            "POST",
            _base(endpoint, f"https://cloudtrail.{region}.amazonaws.com/"),
            raw,
            access_key,
            secret_key,
            session_token,
            region,
            "cloudtrail",
            {
                "content-type": "application/x-amz-json-1.1",
                "x-amz-target": (
                    "com.amazonaws.cloudtrail.v20131101.CloudTrail_20131101.LookupEvents"
                ),
            },
        )
        if status >= 400:
            return _fail("upstream_error", _aws_error(status, payload, headers))
        events = payload.get("Events") if isinstance(payload, dict) else []
        if isinstance(events, list):
            items.extend(
                {
                    "eventId": str(event.get("EventId") or ""),
                    "eventName": str(event.get("EventName") or ""),
                    "eventTime": str(event.get("EventTime") or ""),
                }
                for event in events
                if isinstance(event, dict)
            )
        pages += 1
        token = str(payload.get("NextToken") or "") if isinstance(payload, dict) else ""
        if not token or len(items) >= _ITEM_CAP:
            break
    return _ok({"events": items[:_ITEM_CAP], "pages": pages})


def _signed(  # noqa: PLR0917
    store: Any,
    method: str,
    url: str,
    body: bytes,
    access_key: str,
    secret_key: str,
    session_token: str,
    region: str,
    service: str,
    extra: dict[str, str],
) -> tuple[int, object, dict[str, str]]:
    problem = guard_public(url, allow=["*"], loopback=True)
    if problem:
        return 0, {"error": problem}, {}
    signed = sign_headers(
        method,
        url,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        service=service,
        body=body,
        extra=extra,
        session_token=session_token,
    )
    request_headers = {key: value for key, value in signed.items() if key != "host"}
    transport = getattr(store, "connector_transport", None)
    kwargs: dict[str, object] = {"timeout": 20.0, "follow_redirects": False}
    if transport is not None:
        kwargs["transport"] = transport
    try:
        with httpx.Client(**kwargs) as client:  # type: ignore[arg-type]
            response = blocking(
                client.request, method, url, headers=request_headers, content=body or None
            )
    except httpx.HTTPError:
        return 0, {"error": "AWS did not answer. Check the region and the endpoint."}, {}
    return response.status_code, _payload(response), dict(response.headers.items())


def _payload(response: httpx.Response) -> object:
    raw = response.content[:1_000_000]
    if raw[:1] in {b"{", b"["}:
        try:
            return orjson.loads(raw)
        except orjson.JSONDecodeError:
            return {}
    if raw[:1] == b"<":
        try:
            return ElementTree.fromstring(raw)  # noqa: S314 — the body is the provider's XML
        except ElementTree.ParseError:
            return {}
    return {}


def _instances(payload: object) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not isinstance(payload, ElementTree.Element):
        return rows
    for element in payload.iter():
        if _local(element.tag) not in {"item", "member"}:
            continue
        instance_id = ""
        state = ""
        for child in element:
            if _local(child.tag) == "instanceId":
                instance_id = child.text or ""
            if _local(child.tag) == "instanceState":
                for sub in child:
                    if _local(sub.tag) == "name":
                        state = sub.text or ""
        if instance_id:
            rows.append({"instanceId": instance_id, "state": state})
    return rows


def _policies(payload: object) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not isinstance(payload, ElementTree.Element):
        return rows
    for element in payload.iter():
        if _local(element.tag) != "member":
            continue
        name = ""
        arn = ""
        for child in element:
            if _local(child.tag) == "PolicyName":
                name = child.text or ""
            if _local(child.tag) == "Arn":
                arn = child.text or ""
        if name:
            rows.append({"policyName": name, "arn": arn})
    return rows


def _children(payload: object, parent: str, child_name: str) -> list[str]:
    if not isinstance(payload, ElementTree.Element):
        return []
    found: list[str] = []
    for element in payload.iter():
        if _local(element.tag) != parent:
            continue
        found.extend(
            child.text for child in element if _local(child.tag) == child_name and child.text
        )
    return found


def _xml_value(payload: object, name: str) -> str:
    if not isinstance(payload, ElementTree.Element):
        return ""
    for element in payload.iter():
        if _local(element.tag) == name and element.text:
            return element.text
    return ""


def _aws_error(status: int, payload: object, headers: dict[str, str]) -> str:
    code = ""
    if isinstance(payload, dict):
        raw = payload.get("error") or payload.get("Code") or payload.get("__type")
        code = str(raw or "")
        if "error" in payload and status == 0:
            return str(payload["error"])
    else:
        code = _xml_value(payload, "Code")
    if code in {
        "Throttling",
        "ThrottlingException",
        "RequestLimitExceeded",
        "TooManyRequestsException",
    }:
        return explain_status(429, headers)
    if code == "SignatureDoesNotMatch":
        return "AWS rejected the signature (403). Check the access key, the secret and the clock."
    if code in {"InvalidClientTokenId", "AuthFailure", "ExpiredToken"}:
        return explain_status(401, headers)
    if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
        return explain_status(403, headers)
    return explain_status(status, headers)


def _cached_role(store: Any, row: dict[str, object]) -> tuple[str, str, str] | None:
    raw = cached_token(store, row)
    if not raw.startswith("{"):
        return None
    try:
        loaded = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return None
    if not isinstance(loaded, dict):
        return None
    key_id = str(loaded.get("accessKeyId") or "")
    key_secret = str(loaded.get("secretAccessKey") or "")
    token = str(loaded.get("sessionToken") or "")
    if key_id and key_secret and token:
        return key_id, key_secret, token
    return None


def _seconds_until(expiration: str) -> int:
    if not expiration:
        return 900
    try:
        stamp = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
    except ValueError:
        return 900
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    seconds = int((stamp - datetime.now(UTC)).total_seconds()) - 60
    return max(seconds, 60)


def _split(username: str, secret: str) -> tuple[str, str, str]:
    lines = secret.split("\n")
    session = lines[1].strip() if len(lines) > 1 else ""
    return username.strip(), lines[0].strip(), session


def _row(store: Any, install: dict[str, object]) -> dict[str, object] | None:
    book = getattr(store, "service_connections", None)
    if not isinstance(book, dict):
        return None
    found = book.get(install.get("connection_id"))
    if isinstance(found, dict):
        return found
    name = str(install.get("connection_name") or "")
    for row in book.values():
        if isinstance(row, dict) and str(row.get("name")) == name:
            return row
    return None


def _config(install: dict[str, object]) -> dict[str, str]:
    raw = install.get("config")
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value is not None}


def _base(endpoint: str, default: str) -> str:
    if endpoint:
        return endpoint if endpoint.endswith("/") else endpoint + "/"
    return default


def _form(fields: dict[str, str]) -> bytes:
    return urlencode(sorted(fields.items()), quote_via=quote).encode()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ok(structured: dict[str, object]) -> dict[str, object]:
    return {"text": orjson.dumps(structured).decode(), "structured": structured, "is_error": False}


def _fail(code: str, text: str) -> dict[str, object]:
    return {"text": text, "structured": {}, "is_error": True, "code": code}
