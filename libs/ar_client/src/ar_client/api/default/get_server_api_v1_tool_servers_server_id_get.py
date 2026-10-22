from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_server_api_v1_tool_servers_server_id_get_response_get_server_api_v1_tool_servers_server_id_get import (
    GetServerApiV1ToolServersServerIdGetResponseGetServerApiV1ToolServersServerIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    server_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/tool-servers/{server_id}".format(
            server_id=quote(str(server_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetServerApiV1ToolServersServerIdGetResponseGetServerApiV1ToolServersServerIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetServerApiV1ToolServersServerIdGetResponseGetServerApiV1ToolServersServerIdGet.from_dict(
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
    GetServerApiV1ToolServersServerIdGetResponseGetServerApiV1ToolServersServerIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    server_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetServerApiV1ToolServersServerIdGetResponseGetServerApiV1ToolServersServerIdGet
    | HTTPValidationError
]:
    """Get Server

    Args:
        server_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetServerApiV1ToolServersServerIdGetResponseGetServerApiV1ToolServersServerIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        server_id=server_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    server_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetServerApiV1ToolServersServerIdGetResponseGetServerApiV1ToolServersServerIdGet
    | HTTPValidationError
    | None
):
    """Get Server

    Args:
        server_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetServerApiV1ToolServersServerIdGetResponseGetServerApiV1ToolServersServerIdGet | HTTPValidationError
    """

    return sync_detailed(
        server_id=server_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    server_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetServerApiV1ToolServersServerIdGetResponseGetServerApiV1ToolServersServerIdGet
    | HTTPValidationError
]:
    """Get Server

    Args:
        server_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetServerApiV1ToolServersServerIdGetResponseGetServerApiV1ToolServersServerIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        server_id=server_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    server_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetServerApiV1ToolServersServerIdGetResponseGetServerApiV1ToolServersServerIdGet
    | HTTPValidationError
    | None
):
    """Get Server

    Args:
        server_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetServerApiV1ToolServersServerIdGetResponseGetServerApiV1ToolServersServerIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            server_id=server_id,
            client=client,
        )
    ).parsed
