from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.memory_patch import MemoryPatch
from ...models.patch_memory_api_v1_memory_fact_id_patch_response_patch_memory_api_v1_memory_fact_id_patch import (
    PatchMemoryApiV1MemoryFactIdPatchResponsePatchMemoryApiV1MemoryFactIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    fact_id: UUID,
    *,
    body: MemoryPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/memory/{fact_id}".format(
            fact_id=quote(str(fact_id), safe=""),
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
    | PatchMemoryApiV1MemoryFactIdPatchResponsePatchMemoryApiV1MemoryFactIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = (
            PatchMemoryApiV1MemoryFactIdPatchResponsePatchMemoryApiV1MemoryFactIdPatch.from_dict(
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
    HTTPValidationError | PatchMemoryApiV1MemoryFactIdPatchResponsePatchMemoryApiV1MemoryFactIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    fact_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: MemoryPatch,
) -> Response[
    HTTPValidationError | PatchMemoryApiV1MemoryFactIdPatchResponsePatchMemoryApiV1MemoryFactIdPatch
]:
    """Patch Memory

    Args:
        fact_id (UUID):
        body (MemoryPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchMemoryApiV1MemoryFactIdPatchResponsePatchMemoryApiV1MemoryFactIdPatch]
    """

    kwargs = _get_kwargs(
        fact_id=fact_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    fact_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: MemoryPatch,
) -> (
    HTTPValidationError
    | PatchMemoryApiV1MemoryFactIdPatchResponsePatchMemoryApiV1MemoryFactIdPatch
    | None
):
    """Patch Memory

    Args:
        fact_id (UUID):
        body (MemoryPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchMemoryApiV1MemoryFactIdPatchResponsePatchMemoryApiV1MemoryFactIdPatch
    """

    return sync_detailed(
        fact_id=fact_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    fact_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: MemoryPatch,
) -> Response[
    HTTPValidationError | PatchMemoryApiV1MemoryFactIdPatchResponsePatchMemoryApiV1MemoryFactIdPatch
]:
    """Patch Memory

    Args:
        fact_id (UUID):
        body (MemoryPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchMemoryApiV1MemoryFactIdPatchResponsePatchMemoryApiV1MemoryFactIdPatch]
    """

    kwargs = _get_kwargs(
        fact_id=fact_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    fact_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: MemoryPatch,
) -> (
    HTTPValidationError
    | PatchMemoryApiV1MemoryFactIdPatchResponsePatchMemoryApiV1MemoryFactIdPatch
    | None
):
    """Patch Memory

    Args:
        fact_id (UUID):
        body (MemoryPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchMemoryApiV1MemoryFactIdPatchResponsePatchMemoryApiV1MemoryFactIdPatch
    """

    return (
        await asyncio_detailed(
            fact_id=fact_id,
            client=client,
            body=body,
        )
    ).parsed
