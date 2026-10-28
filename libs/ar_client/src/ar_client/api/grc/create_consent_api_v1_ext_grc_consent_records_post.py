from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_consent_api_v1_ext_grc_consent_records_post_body import (
    CreateConsentApiV1ExtGrcConsentRecordsPostBody,
)
from ...models.create_consent_api_v1_ext_grc_consent_records_post_response_create_consent_api_v1_ext_grc_consent_records_post import (
    CreateConsentApiV1ExtGrcConsentRecordsPostResponseCreateConsentApiV1ExtGrcConsentRecordsPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    *,
    body: CreateConsentApiV1ExtGrcConsentRecordsPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/consent-records",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateConsentApiV1ExtGrcConsentRecordsPostResponseCreateConsentApiV1ExtGrcConsentRecordsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CreateConsentApiV1ExtGrcConsentRecordsPostResponseCreateConsentApiV1ExtGrcConsentRecordsPost.from_dict(
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
    CreateConsentApiV1ExtGrcConsentRecordsPostResponseCreateConsentApiV1ExtGrcConsentRecordsPost
    | HTTPValidationError
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
    body: CreateConsentApiV1ExtGrcConsentRecordsPostBody,
) -> Response[
    CreateConsentApiV1ExtGrcConsentRecordsPostResponseCreateConsentApiV1ExtGrcConsentRecordsPost
    | HTTPValidationError
]:
    """Create Consent

    Args:
        body (CreateConsentApiV1ExtGrcConsentRecordsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateConsentApiV1ExtGrcConsentRecordsPostResponseCreateConsentApiV1ExtGrcConsentRecordsPost | HTTPValidationError]
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
    body: CreateConsentApiV1ExtGrcConsentRecordsPostBody,
) -> (
    CreateConsentApiV1ExtGrcConsentRecordsPostResponseCreateConsentApiV1ExtGrcConsentRecordsPost
    | HTTPValidationError
    | None
):
    """Create Consent

    Args:
        body (CreateConsentApiV1ExtGrcConsentRecordsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateConsentApiV1ExtGrcConsentRecordsPostResponseCreateConsentApiV1ExtGrcConsentRecordsPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateConsentApiV1ExtGrcConsentRecordsPostBody,
) -> Response[
    CreateConsentApiV1ExtGrcConsentRecordsPostResponseCreateConsentApiV1ExtGrcConsentRecordsPost
    | HTTPValidationError
]:
    """Create Consent

    Args:
        body (CreateConsentApiV1ExtGrcConsentRecordsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateConsentApiV1ExtGrcConsentRecordsPostResponseCreateConsentApiV1ExtGrcConsentRecordsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: CreateConsentApiV1ExtGrcConsentRecordsPostBody,
) -> (
    CreateConsentApiV1ExtGrcConsentRecordsPostResponseCreateConsentApiV1ExtGrcConsentRecordsPost
    | HTTPValidationError
    | None
):
    """Create Consent

    Args:
        body (CreateConsentApiV1ExtGrcConsentRecordsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateConsentApiV1ExtGrcConsentRecordsPostResponseCreateConsentApiV1ExtGrcConsentRecordsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
