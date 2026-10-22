from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.add_documents_api_v1_knowledge_collections_collection_id_documents_post_response_add_documents_api_v1_knowledge_collections_collection_id_documents_post import (
    AddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPostResponseAddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPost,
)
from ...models.document_body import DocumentBody
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    collection_id: UUID,
    *,
    body: DocumentBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/knowledge/collections/{collection_id}/documents".format(
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
    AddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPostResponseAddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 202:
        response_202 = AddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPostResponseAddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPost.from_dict(
            response.json()
        )

        return response_202

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
    AddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPostResponseAddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPost
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
    body: DocumentBody,
) -> Response[
    AddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPostResponseAddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPost
    | HTTPValidationError
]:
    """Add Documents

    Args:
        collection_id (UUID):
        body (DocumentBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPostResponseAddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPost | HTTPValidationError]
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
    body: DocumentBody,
) -> (
    AddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPostResponseAddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPost
    | HTTPValidationError
    | None
):
    """Add Documents

    Args:
        collection_id (UUID):
        body (DocumentBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPostResponseAddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPost | HTTPValidationError
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
    body: DocumentBody,
) -> Response[
    AddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPostResponseAddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPost
    | HTTPValidationError
]:
    """Add Documents

    Args:
        collection_id (UUID):
        body (DocumentBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPostResponseAddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPost | HTTPValidationError]
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
    body: DocumentBody,
) -> (
    AddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPostResponseAddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPost
    | HTTPValidationError
    | None
):
    """Add Documents

    Args:
        collection_id (UUID):
        body (DocumentBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPostResponseAddDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            collection_id=collection_id,
            client=client,
            body=body,
        )
    ).parsed
