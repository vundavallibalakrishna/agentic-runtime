from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.rewrite_body import RewriteBody
from ...models.rewrite_document_api_v1_library_documents_document_id_rewrite_post_response_rewrite_document_api_v1_library_documents_document_id_rewrite_post import (
    RewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePostResponseRewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    document_id: UUID,
    *,
    body: RewriteBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/library-documents/{document_id}:rewrite".format(
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
    | RewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePostResponseRewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePost
    | None
):
    if response.status_code == 200:
        response_200 = RewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePostResponseRewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePost.from_dict(
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
    | RewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePostResponseRewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePost
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
    body: RewriteBody,
) -> Response[
    HTTPValidationError
    | RewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePostResponseRewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePost
]:
    """Rewrite Document

    Args:
        document_id (UUID):
        body (RewriteBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePostResponseRewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePost]
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
    body: RewriteBody,
) -> (
    HTTPValidationError
    | RewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePostResponseRewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePost
    | None
):
    """Rewrite Document

    Args:
        document_id (UUID):
        body (RewriteBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePostResponseRewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePost
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
    body: RewriteBody,
) -> Response[
    HTTPValidationError
    | RewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePostResponseRewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePost
]:
    """Rewrite Document

    Args:
        document_id (UUID):
        body (RewriteBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePostResponseRewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePost]
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
    body: RewriteBody,
) -> (
    HTTPValidationError
    | RewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePostResponseRewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePost
    | None
):
    """Rewrite Document

    Args:
        document_id (UUID):
        body (RewriteBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePostResponseRewriteDocumentApiV1LibraryDocumentsDocumentIdRewritePost
    """

    return (
        await asyncio_detailed(
            document_id=document_id,
            client=client,
            body=body,
        )
    ).parsed
