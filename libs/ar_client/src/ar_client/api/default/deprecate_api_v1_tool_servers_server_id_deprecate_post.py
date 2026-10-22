from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.deprecate_api_v1_tool_servers_server_id_deprecate_post_response_deprecate_api_v1_tool_servers_server_id_deprecate_post import (
    DeprecateApiV1ToolServersServerIdDeprecatePostResponseDeprecateApiV1ToolServersServerIdDeprecatePost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    server_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/tool-servers/{server_id}:deprecate".format(
            server_id=quote(str(server_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeprecateApiV1ToolServersServerIdDeprecatePostResponseDeprecateApiV1ToolServersServerIdDeprecatePost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DeprecateApiV1ToolServersServerIdDeprecatePostResponseDeprecateApiV1ToolServersServerIdDeprecatePost.from_dict(
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
    DeprecateApiV1ToolServersServerIdDeprecatePostResponseDeprecateApiV1ToolServersServerIdDeprecatePost
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
    DeprecateApiV1ToolServersServerIdDeprecatePostResponseDeprecateApiV1ToolServersServerIdDeprecatePost
    | HTTPValidationError
]:
    """Deprecate

    Args:
        server_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeprecateApiV1ToolServersServerIdDeprecatePostResponseDeprecateApiV1ToolServersServerIdDeprecatePost | HTTPValidationError]
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
    DeprecateApiV1ToolServersServerIdDeprecatePostResponseDeprecateApiV1ToolServersServerIdDeprecatePost
    | HTTPValidationError
    | None
):
    """Deprecate

    Args:
        server_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeprecateApiV1ToolServersServerIdDeprecatePostResponseDeprecateApiV1ToolServersServerIdDeprecatePost | HTTPValidationError
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
    DeprecateApiV1ToolServersServerIdDeprecatePostResponseDeprecateApiV1ToolServersServerIdDeprecatePost
    | HTTPValidationError
]:
    """Deprecate

    Args:
        server_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeprecateApiV1ToolServersServerIdDeprecatePostResponseDeprecateApiV1ToolServersServerIdDeprecatePost | HTTPValidationError]
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
    DeprecateApiV1ToolServersServerIdDeprecatePostResponseDeprecateApiV1ToolServersServerIdDeprecatePost
    | HTTPValidationError
    | None
):
    """Deprecate

    Args:
        server_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeprecateApiV1ToolServersServerIdDeprecatePostResponseDeprecateApiV1ToolServersServerIdDeprecatePost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            server_id=server_id,
            client=client,
        )
    ).parsed
