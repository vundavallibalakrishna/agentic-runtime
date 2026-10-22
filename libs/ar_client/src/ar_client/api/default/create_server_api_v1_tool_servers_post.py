from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_server_api_v1_tool_servers_post_response_create_server_api_v1_tool_servers_post import (
    CreateServerApiV1ToolServersPostResponseCreateServerApiV1ToolServersPost,
)
from ...models.http_validation_error import HTTPValidationError
from ...models.server_create import ServerCreate
from typing import cast


def _get_kwargs(
    *,
    body: ServerCreate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/tool-servers",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateServerApiV1ToolServersPostResponseCreateServerApiV1ToolServersPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = (
            CreateServerApiV1ToolServersPostResponseCreateServerApiV1ToolServersPost.from_dict(
                response.json()
            )
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
    CreateServerApiV1ToolServersPostResponseCreateServerApiV1ToolServersPost | HTTPValidationError
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
    body: ServerCreate,
) -> Response[
    CreateServerApiV1ToolServersPostResponseCreateServerApiV1ToolServersPost | HTTPValidationError
]:
    """Create Server

    Args:
        body (ServerCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateServerApiV1ToolServersPostResponseCreateServerApiV1ToolServersPost | HTTPValidationError]
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
    body: ServerCreate,
) -> (
    CreateServerApiV1ToolServersPostResponseCreateServerApiV1ToolServersPost
    | HTTPValidationError
    | None
):
    """Create Server

    Args:
        body (ServerCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateServerApiV1ToolServersPostResponseCreateServerApiV1ToolServersPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ServerCreate,
) -> Response[
    CreateServerApiV1ToolServersPostResponseCreateServerApiV1ToolServersPost | HTTPValidationError
]:
    """Create Server

    Args:
        body (ServerCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateServerApiV1ToolServersPostResponseCreateServerApiV1ToolServersPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: ServerCreate,
) -> (
    CreateServerApiV1ToolServersPostResponseCreateServerApiV1ToolServersPost
    | HTTPValidationError
    | None
):
    """Create Server

    Args:
        body (ServerCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateServerApiV1ToolServersPostResponseCreateServerApiV1ToolServersPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
