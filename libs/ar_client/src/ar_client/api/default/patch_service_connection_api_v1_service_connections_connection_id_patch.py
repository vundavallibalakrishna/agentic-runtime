from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_service_connection_api_v1_service_connections_connection_id_patch_response_patch_service_connection_api_v1_service_connections_connection_id_patch import (
    PatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatchResponsePatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatch,
)
from ...models.service_connection_patch import ServiceConnectionPatch
from typing import cast
from uuid import UUID


def _get_kwargs(
    connection_id: UUID,
    *,
    body: ServiceConnectionPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/service-connections/{connection_id}".format(
            connection_id=quote(str(connection_id), safe=""),
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
    | PatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatchResponsePatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatchResponsePatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatch.from_dict(
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
    | PatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatchResponsePatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatch
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
    body: ServiceConnectionPatch,
) -> Response[
    HTTPValidationError
    | PatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatchResponsePatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatch
]:
    """Patch Service Connection

    Args:
        connection_id (UUID):
        body (ServiceConnectionPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatchResponsePatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatch]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ServiceConnectionPatch,
) -> (
    HTTPValidationError
    | PatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatchResponsePatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatch
    | None
):
    """Patch Service Connection

    Args:
        connection_id (UUID):
        body (ServiceConnectionPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatchResponsePatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatch
    """

    return sync_detailed(
        connection_id=connection_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ServiceConnectionPatch,
) -> Response[
    HTTPValidationError
    | PatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatchResponsePatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatch
]:
    """Patch Service Connection

    Args:
        connection_id (UUID):
        body (ServiceConnectionPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatchResponsePatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatch]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ServiceConnectionPatch,
) -> (
    HTTPValidationError
    | PatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatchResponsePatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatch
    | None
):
    """Patch Service Connection

    Args:
        connection_id (UUID):
        body (ServiceConnectionPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatchResponsePatchServiceConnectionApiV1ServiceConnectionsConnectionIdPatch
    """

    return (
        await asyncio_detailed(
            connection_id=connection_id,
            client=client,
            body=body,
        )
    ).parsed
