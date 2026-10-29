from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_service_connections_api_v1_service_connections_get_response_list_service_connections_api_v1_service_connections_get import (
    ListServiceConnectionsApiV1ServiceConnectionsGetResponseListServiceConnectionsApiV1ServiceConnectionsGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/service-connections",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ListServiceConnectionsApiV1ServiceConnectionsGetResponseListServiceConnectionsApiV1ServiceConnectionsGet
    | None
):
    if response.status_code == 200:
        response_200 = ListServiceConnectionsApiV1ServiceConnectionsGetResponseListServiceConnectionsApiV1ServiceConnectionsGet.from_dict(
            response.json()
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    ListServiceConnectionsApiV1ServiceConnectionsGetResponseListServiceConnectionsApiV1ServiceConnectionsGet
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
) -> Response[
    ListServiceConnectionsApiV1ServiceConnectionsGetResponseListServiceConnectionsApiV1ServiceConnectionsGet
]:
    """List Service Connections

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListServiceConnectionsApiV1ServiceConnectionsGetResponseListServiceConnectionsApiV1ServiceConnectionsGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> (
    ListServiceConnectionsApiV1ServiceConnectionsGetResponseListServiceConnectionsApiV1ServiceConnectionsGet
    | None
):
    """List Service Connections

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListServiceConnectionsApiV1ServiceConnectionsGetResponseListServiceConnectionsApiV1ServiceConnectionsGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ListServiceConnectionsApiV1ServiceConnectionsGetResponseListServiceConnectionsApiV1ServiceConnectionsGet
]:
    """List Service Connections

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListServiceConnectionsApiV1ServiceConnectionsGetResponseListServiceConnectionsApiV1ServiceConnectionsGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> (
    ListServiceConnectionsApiV1ServiceConnectionsGetResponseListServiceConnectionsApiV1ServiceConnectionsGet
    | None
):
    """List Service Connections

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListServiceConnectionsApiV1ServiceConnectionsGetResponseListServiceConnectionsApiV1ServiceConnectionsGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
