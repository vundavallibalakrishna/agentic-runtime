from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_connection_api_v1_data_connections_connection_id_get_response_get_connection_api_v1_data_connections_connection_id_get import (
    GetConnectionApiV1DataConnectionsConnectionIdGetResponseGetConnectionApiV1DataConnectionsConnectionIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    connection_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/data-connections/{connection_id}".format(
            connection_id=quote(str(connection_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetConnectionApiV1DataConnectionsConnectionIdGetResponseGetConnectionApiV1DataConnectionsConnectionIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetConnectionApiV1DataConnectionsConnectionIdGetResponseGetConnectionApiV1DataConnectionsConnectionIdGet.from_dict(
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
    GetConnectionApiV1DataConnectionsConnectionIdGetResponseGetConnectionApiV1DataConnectionsConnectionIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetConnectionApiV1DataConnectionsConnectionIdGetResponseGetConnectionApiV1DataConnectionsConnectionIdGet
    | HTTPValidationError
]:
    """Get Connection

    Args:
        connection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetConnectionApiV1DataConnectionsConnectionIdGetResponseGetConnectionApiV1DataConnectionsConnectionIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetConnectionApiV1DataConnectionsConnectionIdGetResponseGetConnectionApiV1DataConnectionsConnectionIdGet
    | HTTPValidationError
    | None
):
    """Get Connection

    Args:
        connection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetConnectionApiV1DataConnectionsConnectionIdGetResponseGetConnectionApiV1DataConnectionsConnectionIdGet | HTTPValidationError
    """

    return sync_detailed(
        connection_id=connection_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetConnectionApiV1DataConnectionsConnectionIdGetResponseGetConnectionApiV1DataConnectionsConnectionIdGet
    | HTTPValidationError
]:
    """Get Connection

    Args:
        connection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetConnectionApiV1DataConnectionsConnectionIdGetResponseGetConnectionApiV1DataConnectionsConnectionIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetConnectionApiV1DataConnectionsConnectionIdGetResponseGetConnectionApiV1DataConnectionsConnectionIdGet
    | HTTPValidationError
    | None
):
    """Get Connection

    Args:
        connection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetConnectionApiV1DataConnectionsConnectionIdGetResponseGetConnectionApiV1DataConnectionsConnectionIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            connection_id=connection_id,
            client=client,
        )
    ).parsed
