from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_passages_api_v1_library_documents_document_id_passages_get_response_list_passages_api_v1_library_documents_document_id_passages_get import (
    ListPassagesApiV1LibraryDocumentsDocumentIdPassagesGetResponseListPassagesApiV1LibraryDocumentsDocumentIdPassagesGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    document_id: UUID,
    *,
    page_from: int | Unset = 1,
    page_to: int | Unset = 0,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["pageFrom"] = page_from

    params["pageTo"] = page_to

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/library-documents/{document_id}/passages".format(
            document_id=quote(str(document_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListPassagesApiV1LibraryDocumentsDocumentIdPassagesGetResponseListPassagesApiV1LibraryDocumentsDocumentIdPassagesGet
    | None
):
    if response.status_code == 200:
        response_200 = ListPassagesApiV1LibraryDocumentsDocumentIdPassagesGetResponseListPassagesApiV1LibraryDocumentsDocumentIdPassagesGet.from_dict(
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
    | ListPassagesApiV1LibraryDocumentsDocumentIdPassagesGetResponseListPassagesApiV1LibraryDocumentsDocumentIdPassagesGet
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
    page_from: int | Unset = 1,
    page_to: int | Unset = 0,
) -> Response[
    HTTPValidationError
    | ListPassagesApiV1LibraryDocumentsDocumentIdPassagesGetResponseListPassagesApiV1LibraryDocumentsDocumentIdPassagesGet
]:
    """List Passages

    Args:
        document_id (UUID):
        page_from (int | Unset):  Default: 1.
        page_to (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListPassagesApiV1LibraryDocumentsDocumentIdPassagesGetResponseListPassagesApiV1LibraryDocumentsDocumentIdPassagesGet]
    """

    kwargs = _get_kwargs(
        document_id=document_id,
        page_from=page_from,
        page_to=page_to,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    page_from: int | Unset = 1,
    page_to: int | Unset = 0,
) -> (
    HTTPValidationError
    | ListPassagesApiV1LibraryDocumentsDocumentIdPassagesGetResponseListPassagesApiV1LibraryDocumentsDocumentIdPassagesGet
    | None
):
    """List Passages

    Args:
        document_id (UUID):
        page_from (int | Unset):  Default: 1.
        page_to (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListPassagesApiV1LibraryDocumentsDocumentIdPassagesGetResponseListPassagesApiV1LibraryDocumentsDocumentIdPassagesGet
    """

    return sync_detailed(
        document_id=document_id,
        client=client,
        page_from=page_from,
        page_to=page_to,
    ).parsed


async def asyncio_detailed(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    page_from: int | Unset = 1,
    page_to: int | Unset = 0,
) -> Response[
    HTTPValidationError
    | ListPassagesApiV1LibraryDocumentsDocumentIdPassagesGetResponseListPassagesApiV1LibraryDocumentsDocumentIdPassagesGet
]:
    """List Passages

    Args:
        document_id (UUID):
        page_from (int | Unset):  Default: 1.
        page_to (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListPassagesApiV1LibraryDocumentsDocumentIdPassagesGetResponseListPassagesApiV1LibraryDocumentsDocumentIdPassagesGet]
    """

    kwargs = _get_kwargs(
        document_id=document_id,
        page_from=page_from,
        page_to=page_to,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    document_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    page_from: int | Unset = 1,
    page_to: int | Unset = 0,
) -> (
    HTTPValidationError
    | ListPassagesApiV1LibraryDocumentsDocumentIdPassagesGetResponseListPassagesApiV1LibraryDocumentsDocumentIdPassagesGet
    | None
):
    """List Passages

    Args:
        document_id (UUID):
        page_from (int | Unset):  Default: 1.
        page_to (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListPassagesApiV1LibraryDocumentsDocumentIdPassagesGetResponseListPassagesApiV1LibraryDocumentsDocumentIdPassagesGet
    """

    return (
        await asyncio_detailed(
            document_id=document_id,
            client=client,
            page_from=page_from,
            page_to=page_to,
        )
    ).parsed
