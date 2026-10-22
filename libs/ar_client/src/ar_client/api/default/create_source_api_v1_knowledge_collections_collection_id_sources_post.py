from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_source_api_v1_knowledge_collections_collection_id_sources_post_response_create_source_api_v1_knowledge_collections_collection_id_sources_post import (
    CreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPostResponseCreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPost,
)
from ...models.http_validation_error import HTTPValidationError
from ...models.source_body import SourceBody
from typing import cast
from uuid import UUID


def _get_kwargs(
    collection_id: UUID,
    *,
    body: SourceBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/knowledge/collections/{collection_id}/sources".format(
            collection_id=quote(str(collection_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPostResponseCreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPostResponseCreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPost.from_dict(
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
    CreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPostResponseCreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    collection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SourceBody,
) -> Response[
    CreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPostResponseCreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPost
    | HTTPValidationError
]:
    """Create Source

    Args:
        collection_id (UUID):
        body (SourceBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPostResponseCreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        collection_id=collection_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    collection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SourceBody,
) -> (
    CreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPostResponseCreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPost
    | HTTPValidationError
    | None
):
    """Create Source

    Args:
        collection_id (UUID):
        body (SourceBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPostResponseCreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPost | HTTPValidationError
    """

    return sync_detailed(
        collection_id=collection_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    collection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SourceBody,
) -> Response[
    CreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPostResponseCreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPost
    | HTTPValidationError
]:
    """Create Source

    Args:
        collection_id (UUID):
        body (SourceBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPostResponseCreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        collection_id=collection_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    collection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SourceBody,
) -> (
    CreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPostResponseCreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPost
    | HTTPValidationError
    | None
):
    """Create Source

    Args:
        collection_id (UUID):
        body (SourceBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPostResponseCreateSourceApiV1KnowledgeCollectionsCollectionIdSourcesPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            collection_id=collection_id,
            client=client,
            body=body,
        )
    ).parsed
