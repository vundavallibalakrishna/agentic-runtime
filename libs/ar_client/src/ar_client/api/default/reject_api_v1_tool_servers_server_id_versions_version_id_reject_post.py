from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.notes_body import NotesBody
from ...models.reject_api_v1_tool_servers_server_id_versions_version_id_reject_post_response_reject_api_v1_tool_servers_server_id_versions_version_id_reject_post import (
    RejectApiV1ToolServersServerIdVersionsVersionIdRejectPostResponseRejectApiV1ToolServersServerIdVersionsVersionIdRejectPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    server_id: UUID,
    version_id: UUID,
    *,
    body: NotesBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/tool-servers/{server_id}/versions/{version_id}:reject".format(
            server_id=quote(str(server_id), safe=""),
            version_id=quote(str(version_id), safe=""),
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
    | RejectApiV1ToolServersServerIdVersionsVersionIdRejectPostResponseRejectApiV1ToolServersServerIdVersionsVersionIdRejectPost
    | None
):
    if response.status_code == 200:
        response_200 = RejectApiV1ToolServersServerIdVersionsVersionIdRejectPostResponseRejectApiV1ToolServersServerIdVersionsVersionIdRejectPost.from_dict(
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
    | RejectApiV1ToolServersServerIdVersionsVersionIdRejectPostResponseRejectApiV1ToolServersServerIdVersionsVersionIdRejectPost
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
    *,
    client: AuthenticatedClient | Client,
    body: NotesBody,
) -> Response[
    HTTPValidationError
    | RejectApiV1ToolServersServerIdVersionsVersionIdRejectPostResponseRejectApiV1ToolServersServerIdVersionsVersionIdRejectPost
]:
    """Reject

    Args:
        server_id (UUID):
        version_id (UUID):
        body (NotesBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RejectApiV1ToolServersServerIdVersionsVersionIdRejectPostResponseRejectApiV1ToolServersServerIdVersionsVersionIdRejectPost]
    """

    kwargs = _get_kwargs(
        server_id=server_id,
        version_id=version_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    server_id: UUID,
    version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: NotesBody,
) -> (
    HTTPValidationError
    | RejectApiV1ToolServersServerIdVersionsVersionIdRejectPostResponseRejectApiV1ToolServersServerIdVersionsVersionIdRejectPost
    | None
):
    """Reject

    Args:
        server_id (UUID):
        version_id (UUID):
        body (NotesBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RejectApiV1ToolServersServerIdVersionsVersionIdRejectPostResponseRejectApiV1ToolServersServerIdVersionsVersionIdRejectPost
    """

    return sync_detailed(
        server_id=server_id,
        version_id=version_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    server_id: UUID,
    version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: NotesBody,
) -> Response[
    HTTPValidationError
    | RejectApiV1ToolServersServerIdVersionsVersionIdRejectPostResponseRejectApiV1ToolServersServerIdVersionsVersionIdRejectPost
]:
    """Reject

    Args:
        server_id (UUID):
        version_id (UUID):
        body (NotesBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RejectApiV1ToolServersServerIdVersionsVersionIdRejectPostResponseRejectApiV1ToolServersServerIdVersionsVersionIdRejectPost]
    """

    kwargs = _get_kwargs(
        server_id=server_id,
        version_id=version_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    server_id: UUID,
    version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: NotesBody,
) -> (
    HTTPValidationError
    | RejectApiV1ToolServersServerIdVersionsVersionIdRejectPostResponseRejectApiV1ToolServersServerIdVersionsVersionIdRejectPost
    | None
):
    """Reject

    Args:
        server_id (UUID):
        version_id (UUID):
        body (NotesBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RejectApiV1ToolServersServerIdVersionsVersionIdRejectPostResponseRejectApiV1ToolServersServerIdVersionsVersionIdRejectPost
    """

    return (
        await asyncio_detailed(
            server_id=server_id,
            version_id=version_id,
            client=client,
            body=body,
        )
    ).parsed
