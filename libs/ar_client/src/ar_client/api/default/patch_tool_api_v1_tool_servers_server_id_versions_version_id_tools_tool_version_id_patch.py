from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_tool_api_v1_tool_servers_server_id_versions_version_id_tools_tool_version_id_patch_response_patch_tool_api_v1_tool_servers_server_id_versions_version_id_tools_tool_version_id_patch import (
    PatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatchResponsePatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatch,
)
from ...models.tool_patch import ToolPatch
from typing import cast
from uuid import UUID


def _get_kwargs(
    server_id: UUID,
    version_id: UUID,
    tool_version_id: UUID,
    *,
    body: ToolPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/tool-servers/{server_id}/versions/{version_id}/tools/{tool_version_id}".format(
            server_id=quote(str(server_id), safe=""),
            version_id=quote(str(version_id), safe=""),
            tool_version_id=quote(str(tool_version_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | PatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatchResponsePatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatchResponsePatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatch.from_dict(
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
    | PatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatchResponsePatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    server_id: UUID,
    version_id: UUID,
    tool_version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ToolPatch,
) -> Response[
    HTTPValidationError
    | PatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatchResponsePatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatch
]:
    """Patch Tool

    Args:
        server_id (UUID):
        version_id (UUID):
        tool_version_id (UUID):
        body (ToolPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatchResponsePatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatch]
    """

    kwargs = _get_kwargs(
        server_id=server_id,
        version_id=version_id,
        tool_version_id=tool_version_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    server_id: UUID,
    version_id: UUID,
    tool_version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ToolPatch,
) -> (
    HTTPValidationError
    | PatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatchResponsePatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatch
    | None
):
    """Patch Tool

    Args:
        server_id (UUID):
        version_id (UUID):
        tool_version_id (UUID):
        body (ToolPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatchResponsePatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatch
    """

    return sync_detailed(
        server_id=server_id,
        version_id=version_id,
        tool_version_id=tool_version_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    server_id: UUID,
    version_id: UUID,
    tool_version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ToolPatch,
) -> Response[
    HTTPValidationError
    | PatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatchResponsePatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatch
]:
    """Patch Tool

    Args:
        server_id (UUID):
        version_id (UUID):
        tool_version_id (UUID):
        body (ToolPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatchResponsePatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatch]
    """

    kwargs = _get_kwargs(
        server_id=server_id,
        version_id=version_id,
        tool_version_id=tool_version_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    server_id: UUID,
    version_id: UUID,
    tool_version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ToolPatch,
) -> (
    HTTPValidationError
    | PatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatchResponsePatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatch
    | None
):
    """Patch Tool

    Args:
        server_id (UUID):
        version_id (UUID):
        tool_version_id (UUID):
        body (ToolPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatchResponsePatchToolApiV1ToolServersServerIdVersionsVersionIdToolsToolVersionIdPatch
    """

    return (
        await asyncio_detailed(
            server_id=server_id,
            version_id=version_id,
            tool_version_id=tool_version_id,
            client=client,
            body=body,
        )
    ).parsed
