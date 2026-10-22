from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_collection_api_v1_knowledge_collections_collection_id_get_response_get_collection_api_v1_knowledge_collections_collection_id_get import (
    GetCollectionApiV1KnowledgeCollectionsCollectionIdGetResponseGetCollectionApiV1KnowledgeCollectionsCollectionIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    collection_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/knowledge/collections/{collection_id}".format(
            collection_id=quote(str(collection_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetCollectionApiV1KnowledgeCollectionsCollectionIdGetResponseGetCollectionApiV1KnowledgeCollectionsCollectionIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetCollectionApiV1KnowledgeCollectionsCollectionIdGetResponseGetCollectionApiV1KnowledgeCollectionsCollectionIdGet.from_dict(
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
    GetCollectionApiV1KnowledgeCollectionsCollectionIdGetResponseGetCollectionApiV1KnowledgeCollectionsCollectionIdGet
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
) -> Response[
    GetCollectionApiV1KnowledgeCollectionsCollectionIdGetResponseGetCollectionApiV1KnowledgeCollectionsCollectionIdGet
    | HTTPValidationError
]:
    """Get Collection

    Args:
        collection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetCollectionApiV1KnowledgeCollectionsCollectionIdGetResponseGetCollectionApiV1KnowledgeCollectionsCollectionIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        collection_id=collection_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    collection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetCollectionApiV1KnowledgeCollectionsCollectionIdGetResponseGetCollectionApiV1KnowledgeCollectionsCollectionIdGet
    | HTTPValidationError
    | None
):
    """Get Collection

    Args:
        collection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetCollectionApiV1KnowledgeCollectionsCollectionIdGetResponseGetCollectionApiV1KnowledgeCollectionsCollectionIdGet | HTTPValidationError
    """

    return sync_detailed(
        collection_id=collection_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    collection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetCollectionApiV1KnowledgeCollectionsCollectionIdGetResponseGetCollectionApiV1KnowledgeCollectionsCollectionIdGet
    | HTTPValidationError
]:
    """Get Collection

    Args:
        collection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetCollectionApiV1KnowledgeCollectionsCollectionIdGetResponseGetCollectionApiV1KnowledgeCollectionsCollectionIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        collection_id=collection_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    collection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetCollectionApiV1KnowledgeCollectionsCollectionIdGetResponseGetCollectionApiV1KnowledgeCollectionsCollectionIdGet
    | HTTPValidationError
    | None
):
    """Get Collection

    Args:
        collection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetCollectionApiV1KnowledgeCollectionsCollectionIdGetResponseGetCollectionApiV1KnowledgeCollectionsCollectionIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            collection_id=collection_id,
            client=client,
        )
    ).parsed
