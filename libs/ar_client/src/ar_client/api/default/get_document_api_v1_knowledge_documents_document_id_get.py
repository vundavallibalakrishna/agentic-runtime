from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_document_api_v1_knowledge_documents_document_id_get_response_get_document_api_v1_knowledge_documents_document_id_get import (
    GetDocumentApiV1KnowledgeDocumentsDocumentIdGetResponseGetDocumentApiV1KnowledgeDocumentsDocumentIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    document_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/knowledge/documents/{document_id}".format(
            document_id=quote(str(document_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetDocumentApiV1KnowledgeDocumentsDocumentIdGetResponseGetDocumentApiV1KnowledgeDocumentsDocumentIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetDocumentApiV1KnowledgeDocumentsDocumentIdGetResponseGetDocumentApiV1KnowledgeDocumentsDocumentIdGet.from_dict(
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
    GetDocumentApiV1KnowledgeDocumentsDocumentIdGetResponseGetDocumentApiV1KnowledgeDocumentsDocumentIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetDocumentApiV1KnowledgeDocumentsDocumentIdGetResponseGetDocumentApiV1KnowledgeDocumentsDocumentIdGet
    | HTTPValidationError
]:
    """Get Document

    Args:
        document_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetDocumentApiV1KnowledgeDocumentsDocumentIdGetResponseGetDocumentApiV1KnowledgeDocumentsDocumentIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        document_id=document_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetDocumentApiV1KnowledgeDocumentsDocumentIdGetResponseGetDocumentApiV1KnowledgeDocumentsDocumentIdGet
    | HTTPValidationError
    | None
):
    """Get Document

    Args:
        document_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetDocumentApiV1KnowledgeDocumentsDocumentIdGetResponseGetDocumentApiV1KnowledgeDocumentsDocumentIdGet | HTTPValidationError
    """

    return sync_detailed(
        document_id=document_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetDocumentApiV1KnowledgeDocumentsDocumentIdGetResponseGetDocumentApiV1KnowledgeDocumentsDocumentIdGet
    | HTTPValidationError
]:
    """Get Document

    Args:
        document_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetDocumentApiV1KnowledgeDocumentsDocumentIdGetResponseGetDocumentApiV1KnowledgeDocumentsDocumentIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        document_id=document_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetDocumentApiV1KnowledgeDocumentsDocumentIdGetResponseGetDocumentApiV1KnowledgeDocumentsDocumentIdGet
    | HTTPValidationError
    | None
):
    """Get Document

    Args:
        document_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetDocumentApiV1KnowledgeDocumentsDocumentIdGetResponseGetDocumentApiV1KnowledgeDocumentsDocumentIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            document_id=document_id,
            client=client,
        )
    ).parsed
