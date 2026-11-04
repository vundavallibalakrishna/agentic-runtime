from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.fulfil_dsar_api_v1_ext_grc_dsar_requests_request_id_fulfil_post_response_fulfil_dsar_api_v1_ext_grc_dsar_requests_request_id_fulfil_post import (
    FulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPostResponseFulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    request_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/dsar-requests/{request_id}:fulfil".format(
            request_id=quote(str(request_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    FulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPostResponseFulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = FulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPostResponseFulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPost.from_dict(
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
    FulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPostResponseFulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    request_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    FulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPostResponseFulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPost
    | HTTPValidationError
]:
    """Fulfil Dsar

    Args:
        request_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[FulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPostResponseFulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        request_id=request_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    request_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    FulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPostResponseFulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPost
    | HTTPValidationError
    | None
):
    """Fulfil Dsar

    Args:
        request_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        FulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPostResponseFulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPost | HTTPValidationError
    """

    return sync_detailed(
        request_id=request_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    request_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    FulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPostResponseFulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPost
    | HTTPValidationError
]:
    """Fulfil Dsar

    Args:
        request_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[FulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPostResponseFulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        request_id=request_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    request_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    FulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPostResponseFulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPost
    | HTTPValidationError
    | None
):
    """Fulfil Dsar

    Args:
        request_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        FulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPostResponseFulfilDsarApiV1ExtGrcDsarRequestsRequestIdFulfilPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            request_id=request_id,
            client=client,
        )
    ).parsed
