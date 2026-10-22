from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_version_api_v1_tool_servers_server_id_versions_post_response_create_version_api_v1_tool_servers_server_id_versions_post import (
    CreateVersionApiV1ToolServersServerIdVersionsPostResponseCreateVersionApiV1ToolServersServerIdVersionsPost,
)
from ...models.http_validation_error import HTTPValidationError
from ...models.version_body import VersionBody
from typing import cast
from uuid import UUID


def _get_kwargs(
    server_id: UUID,
    *,
    body: VersionBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/tool-servers/{server_id}/versions".format(
            server_id=quote(str(server_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateVersionApiV1ToolServersServerIdVersionsPostResponseCreateVersionApiV1ToolServersServerIdVersionsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CreateVersionApiV1ToolServersServerIdVersionsPostResponseCreateVersionApiV1ToolServersServerIdVersionsPost.from_dict(
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
    CreateVersionApiV1ToolServersServerIdVersionsPostResponseCreateVersionApiV1ToolServersServerIdVersionsPost
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
    body: VersionBody,
) -> Response[
    CreateVersionApiV1ToolServersServerIdVersionsPostResponseCreateVersionApiV1ToolServersServerIdVersionsPost
    | HTTPValidationError
]:
    """Create Version

    Args:
        server_id (UUID):
        body (VersionBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateVersionApiV1ToolServersServerIdVersionsPostResponseCreateVersionApiV1ToolServersServerIdVersionsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        server_id=server_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    server_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: VersionBody,
) -> (
    CreateVersionApiV1ToolServersServerIdVersionsPostResponseCreateVersionApiV1ToolServersServerIdVersionsPost
    | HTTPValidationError
    | None
):
    """Create Version

    Args:
        server_id (UUID):
        body (VersionBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateVersionApiV1ToolServersServerIdVersionsPostResponseCreateVersionApiV1ToolServersServerIdVersionsPost | HTTPValidationError
    """

    return sync_detailed(
        server_id=server_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    server_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: VersionBody,
) -> Response[
    CreateVersionApiV1ToolServersServerIdVersionsPostResponseCreateVersionApiV1ToolServersServerIdVersionsPost
    | HTTPValidationError
]:
    """Create Version

    Args:
        server_id (UUID):
        body (VersionBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateVersionApiV1ToolServersServerIdVersionsPostResponseCreateVersionApiV1ToolServersServerIdVersionsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        server_id=server_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    server_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: VersionBody,
) -> (
    CreateVersionApiV1ToolServersServerIdVersionsPostResponseCreateVersionApiV1ToolServersServerIdVersionsPost
    | HTTPValidationError
    | None
):
    """Create Version

    Args:
        server_id (UUID):
        body (VersionBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateVersionApiV1ToolServersServerIdVersionsPostResponseCreateVersionApiV1ToolServersServerIdVersionsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            server_id=server_id,
            client=client,
            body=body,
        )
    ).parsed
