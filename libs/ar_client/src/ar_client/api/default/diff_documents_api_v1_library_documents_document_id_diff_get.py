from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.diff_documents_api_v1_library_documents_document_id_diff_get_response_diff_documents_api_v1_library_documents_document_id_diff_get import (
    DiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGetResponseDiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    document_id: UUID,
    *,
    other_document_id: UUID,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_other_document_id = str(other_document_id)
    params["otherDocumentId"] = json_other_document_id

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/library-documents/{document_id}/diff".format(
            document_id=quote(str(document_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGetResponseDiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGetResponseDiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGet.from_dict(
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
    DiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGetResponseDiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGet
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
    other_document_id: UUID,
) -> Response[
    DiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGetResponseDiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGet
    | HTTPValidationError
]:
    """Diff Documents

     The sections that differ between this document and another. No model is asked.

    Args:
        document_id (UUID):
        other_document_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGetResponseDiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        document_id=document_id,
        other_document_id=other_document_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    other_document_id: UUID,
) -> (
    DiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGetResponseDiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGet
    | HTTPValidationError
    | None
):
    """Diff Documents

     The sections that differ between this document and another. No model is asked.

    Args:
        document_id (UUID):
        other_document_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGetResponseDiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGet | HTTPValidationError
    """

    return sync_detailed(
        document_id=document_id,
        client=client,
        other_document_id=other_document_id,
    ).parsed


async def asyncio_detailed(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    other_document_id: UUID,
) -> Response[
    DiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGetResponseDiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGet
    | HTTPValidationError
]:
    """Diff Documents

     The sections that differ between this document and another. No model is asked.

    Args:
        document_id (UUID):
        other_document_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGetResponseDiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        document_id=document_id,
        other_document_id=other_document_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    other_document_id: UUID,
) -> (
    DiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGetResponseDiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGet
    | HTTPValidationError
    | None
):
    """Diff Documents

     The sections that differ between this document and another. No model is asked.

    Args:
        document_id (UUID):
        other_document_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGetResponseDiffDocumentsApiV1LibraryDocumentsDocumentIdDiffGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            document_id=document_id,
            client=client,
            other_document_id=other_document_id,
        )
    ).parsed
