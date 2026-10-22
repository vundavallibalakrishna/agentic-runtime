from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_source_api_v1_knowledge_sources_source_id_patch_response_patch_source_api_v1_knowledge_sources_source_id_patch import (
    PatchSourceApiV1KnowledgeSourcesSourceIdPatchResponsePatchSourceApiV1KnowledgeSourcesSourceIdPatch,
)
from ...models.source_patch import SourcePatch
from typing import cast
from uuid import UUID


def _get_kwargs(
    source_id: UUID,
    *,
    body: SourcePatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/knowledge/sources/{source_id}".format(
            source_id=quote(str(source_id), safe=""),
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
    | PatchSourceApiV1KnowledgeSourcesSourceIdPatchResponsePatchSourceApiV1KnowledgeSourcesSourceIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchSourceApiV1KnowledgeSourcesSourceIdPatchResponsePatchSourceApiV1KnowledgeSourcesSourceIdPatch.from_dict(
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
    | PatchSourceApiV1KnowledgeSourcesSourceIdPatchResponsePatchSourceApiV1KnowledgeSourcesSourceIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    source_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SourcePatch,
) -> Response[
    HTTPValidationError
    | PatchSourceApiV1KnowledgeSourcesSourceIdPatchResponsePatchSourceApiV1KnowledgeSourcesSourceIdPatch
]:
    """Patch Source

    Args:
        source_id (UUID):
        body (SourcePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchSourceApiV1KnowledgeSourcesSourceIdPatchResponsePatchSourceApiV1KnowledgeSourcesSourceIdPatch]
    """

    kwargs = _get_kwargs(
        source_id=source_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    source_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SourcePatch,
) -> (
    HTTPValidationError
    | PatchSourceApiV1KnowledgeSourcesSourceIdPatchResponsePatchSourceApiV1KnowledgeSourcesSourceIdPatch
    | None
):
    """Patch Source

    Args:
        source_id (UUID):
        body (SourcePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchSourceApiV1KnowledgeSourcesSourceIdPatchResponsePatchSourceApiV1KnowledgeSourcesSourceIdPatch
    """

    return sync_detailed(
        source_id=source_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    source_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SourcePatch,
) -> Response[
    HTTPValidationError
    | PatchSourceApiV1KnowledgeSourcesSourceIdPatchResponsePatchSourceApiV1KnowledgeSourcesSourceIdPatch
]:
    """Patch Source

    Args:
        source_id (UUID):
        body (SourcePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchSourceApiV1KnowledgeSourcesSourceIdPatchResponsePatchSourceApiV1KnowledgeSourcesSourceIdPatch]
    """

    kwargs = _get_kwargs(
        source_id=source_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    source_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SourcePatch,
) -> (
    HTTPValidationError
    | PatchSourceApiV1KnowledgeSourcesSourceIdPatchResponsePatchSourceApiV1KnowledgeSourcesSourceIdPatch
    | None
):
    """Patch Source

    Args:
        source_id (UUID):
        body (SourcePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchSourceApiV1KnowledgeSourcesSourceIdPatchResponsePatchSourceApiV1KnowledgeSourcesSourceIdPatch
    """

    return (
        await asyncio_detailed(
            source_id=source_id,
            client=client,
            body=body,
        )
    ).parsed
