from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.ingest_entitlements_api_v1_ext_grc_entitlements_ingest_post_body import (
    IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostBody,
)
from ...models.ingest_entitlements_api_v1_ext_grc_entitlements_ingest_post_response_ingest_entitlements_api_v1_ext_grc_entitlements_ingest_post import (
    IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostResponseIngestEntitlementsApiV1ExtGrcEntitlementsIngestPost,
)
from typing import cast


def _get_kwargs(
    *,
    body: IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/entitlements:ingest",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostResponseIngestEntitlementsApiV1ExtGrcEntitlementsIngestPost
    | None
):
    if response.status_code == 200:
        response_200 = IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostResponseIngestEntitlementsApiV1ExtGrcEntitlementsIngestPost.from_dict(
            response.json()
        )

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    HTTPValidationError
    | IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostResponseIngestEntitlementsApiV1ExtGrcEntitlementsIngestPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostBody,
) -> Response[
    HTTPValidationError
    | IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostResponseIngestEntitlementsApiV1ExtGrcEntitlementsIngestPost
]:
    """Ingest Entitlements

    Args:
        body (IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostResponseIngestEntitlementsApiV1ExtGrcEntitlementsIngestPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostBody,
) -> (
    HTTPValidationError
    | IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostResponseIngestEntitlementsApiV1ExtGrcEntitlementsIngestPost
    | None
):
    """Ingest Entitlements

    Args:
        body (IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostResponseIngestEntitlementsApiV1ExtGrcEntitlementsIngestPost
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostBody,
) -> Response[
    HTTPValidationError
    | IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostResponseIngestEntitlementsApiV1ExtGrcEntitlementsIngestPost
]:
    """Ingest Entitlements

    Args:
        body (IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostResponseIngestEntitlementsApiV1ExtGrcEntitlementsIngestPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostBody,
) -> (
    HTTPValidationError
    | IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostResponseIngestEntitlementsApiV1ExtGrcEntitlementsIngestPost
    | None
):
    """Ingest Entitlements

    Args:
        body (IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | IngestEntitlementsApiV1ExtGrcEntitlementsIngestPostResponseIngestEntitlementsApiV1ExtGrcEntitlementsIngestPost
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
