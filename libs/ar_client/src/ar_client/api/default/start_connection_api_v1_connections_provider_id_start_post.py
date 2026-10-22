from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.start_connection_api_v1_connections_provider_id_start_post_response_start_connection_api_v1_connections_provider_id_start_post import (
    StartConnectionApiV1ConnectionsProviderIdStartPostResponseStartConnectionApiV1ConnectionsProviderIdStartPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    provider_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/connections/{provider_id}:start".format(
            provider_id=quote(str(provider_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | StartConnectionApiV1ConnectionsProviderIdStartPostResponseStartConnectionApiV1ConnectionsProviderIdStartPost
    | None
):
    if response.status_code == 200:
        response_200 = StartConnectionApiV1ConnectionsProviderIdStartPostResponseStartConnectionApiV1ConnectionsProviderIdStartPost.from_dict(
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
    | StartConnectionApiV1ConnectionsProviderIdStartPostResponseStartConnectionApiV1ConnectionsProviderIdStartPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    provider_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | StartConnectionApiV1ConnectionsProviderIdStartPostResponseStartConnectionApiV1ConnectionsProviderIdStartPost
]:
    """Start Connection

    Args:
        provider_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | StartConnectionApiV1ConnectionsProviderIdStartPostResponseStartConnectionApiV1ConnectionsProviderIdStartPost]
    """

    kwargs = _get_kwargs(
        provider_id=provider_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    provider_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | StartConnectionApiV1ConnectionsProviderIdStartPostResponseStartConnectionApiV1ConnectionsProviderIdStartPost
    | None
):
    """Start Connection

    Args:
        provider_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | StartConnectionApiV1ConnectionsProviderIdStartPostResponseStartConnectionApiV1ConnectionsProviderIdStartPost
    """

    return sync_detailed(
        provider_id=provider_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    provider_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | StartConnectionApiV1ConnectionsProviderIdStartPostResponseStartConnectionApiV1ConnectionsProviderIdStartPost
]:
    """Start Connection

    Args:
        provider_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | StartConnectionApiV1ConnectionsProviderIdStartPostResponseStartConnectionApiV1ConnectionsProviderIdStartPost]
    """

    kwargs = _get_kwargs(
        provider_id=provider_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    provider_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | StartConnectionApiV1ConnectionsProviderIdStartPostResponseStartConnectionApiV1ConnectionsProviderIdStartPost
    | None
):
    """Start Connection

    Args:
        provider_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | StartConnectionApiV1ConnectionsProviderIdStartPostResponseStartConnectionApiV1ConnectionsProviderIdStartPost
    """

    return (
        await asyncio_detailed(
            provider_id=provider_id,
            client=client,
        )
    ).parsed
