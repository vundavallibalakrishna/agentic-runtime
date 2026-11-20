from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.reprocess_body import ReprocessBody
from ...models.reprocess_library_document_api_v1_library_documents_document_id_reprocess_post_response_reprocess_library_document_api_v1_library_documents_document_id_reprocess_post import (
    ReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPostResponseReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    document_id: UUID,
    *,
    body: ReprocessBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/library-documents/{document_id}:reprocess".format(
            document_id=quote(str(document_id), safe=""),
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
    | ReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPostResponseReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPost
    | None
):
    if response.status_code == 200:
        response_200 = ReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPostResponseReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPost.from_dict(
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
    | ReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPostResponseReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPost
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
    body: ReprocessBody,
) -> Response[
    HTTPValidationError
    | ReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPostResponseReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPost
]:
    """Reprocess Library Document

    Args:
        document_id (UUID):
        body (ReprocessBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPostResponseReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPost]
    """

    kwargs = _get_kwargs(
        document_id=document_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReprocessBody,
) -> (
    HTTPValidationError
    | ReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPostResponseReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPost
    | None
):
    """Reprocess Library Document

    Args:
        document_id (UUID):
        body (ReprocessBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPostResponseReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPost
    """

    return sync_detailed(
        document_id=document_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReprocessBody,
) -> Response[
    HTTPValidationError
    | ReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPostResponseReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPost
]:
    """Reprocess Library Document

    Args:
        document_id (UUID):
        body (ReprocessBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPostResponseReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPost]
    """

    kwargs = _get_kwargs(
        document_id=document_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReprocessBody,
) -> (
    HTTPValidationError
    | ReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPostResponseReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPost
    | None
):
    """Reprocess Library Document

    Args:
        document_id (UUID):
        body (ReprocessBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPostResponseReprocessLibraryDocumentApiV1LibraryDocumentsDocumentIdReprocessPost
    """

    return (
        await asyncio_detailed(
            document_id=document_id,
            client=client,
            body=body,
        )
    ).parsed
