from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_documents_api_v1_knowledge_collections_collection_id_documents_get_response_list_documents_api_v1_knowledge_collections_collection_id_documents_get import (
    ListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGetResponseListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    collection_id: UUID,
    *,
    q: str | Unset = "",
    status: str | Unset = "",
    source_id: None | Unset | UUID = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

    params["status"] = status

    json_source_id: None | str | Unset
    if isinstance(source_id, Unset):
        json_source_id = UNSET
    elif isinstance(source_id, UUID):
        json_source_id = str(source_id)
    else:
        json_source_id = source_id
    params["source_id"] = json_source_id

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/knowledge/collections/{collection_id}/documents".format(
            collection_id=quote(str(collection_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGetResponseListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGet
    | None
):
    if response.status_code == 200:
        response_200 = ListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGetResponseListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGet.from_dict(
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
    | ListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGetResponseListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGet
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
    q: str | Unset = "",
    status: str | Unset = "",
    source_id: None | Unset | UUID = UNSET,
) -> Response[
    HTTPValidationError
    | ListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGetResponseListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGet
]:
    """List Documents

    Args:
        collection_id (UUID):
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: ''.
        source_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGetResponseListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGet]
    """

    kwargs = _get_kwargs(
        collection_id=collection_id,
        q=q,
        status=status,
        source_id=source_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    collection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: str | Unset = "",
    source_id: None | Unset | UUID = UNSET,
) -> (
    HTTPValidationError
    | ListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGetResponseListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGet
    | None
):
    """List Documents

    Args:
        collection_id (UUID):
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: ''.
        source_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGetResponseListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGet
    """

    return sync_detailed(
        collection_id=collection_id,
        client=client,
        q=q,
        status=status,
        source_id=source_id,
    ).parsed


async def asyncio_detailed(
    collection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: str | Unset = "",
    source_id: None | Unset | UUID = UNSET,
) -> Response[
    HTTPValidationError
    | ListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGetResponseListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGet
]:
    """List Documents

    Args:
        collection_id (UUID):
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: ''.
        source_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGetResponseListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGet]
    """

    kwargs = _get_kwargs(
        collection_id=collection_id,
        q=q,
        status=status,
        source_id=source_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    collection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: str | Unset = "",
    source_id: None | Unset | UUID = UNSET,
) -> (
    HTTPValidationError
    | ListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGetResponseListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGet
    | None
):
    """List Documents

    Args:
        collection_id (UUID):
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: ''.
        source_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGetResponseListDocumentsApiV1KnowledgeCollectionsCollectionIdDocumentsGet
    """

    return (
        await asyncio_detailed(
            collection_id=collection_id,
            client=client,
            q=q,
            status=status,
            source_id=source_id,
        )
    ).parsed
