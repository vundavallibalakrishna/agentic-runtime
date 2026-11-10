from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.judge_body import JudgeBody
from ...models.judge_document_api_v1_library_documents_document_id_judge_post_response_judge_document_api_v1_library_documents_document_id_judge_post import (
    JudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePostResponseJudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    document_id: UUID,
    *,
    body: JudgeBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/library-documents/{document_id}:judge".format(
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
    | JudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePostResponseJudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePost
    | None
):
    if response.status_code == 200:
        response_200 = JudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePostResponseJudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePost.from_dict(
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
    | JudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePostResponseJudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePost
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
    body: JudgeBody,
) -> Response[
    HTTPValidationError
    | JudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePostResponseJudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePost
]:
    """Judge Document

    Args:
        document_id (UUID):
        body (JudgeBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | JudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePostResponseJudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePost]
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
    body: JudgeBody,
) -> (
    HTTPValidationError
    | JudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePostResponseJudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePost
    | None
):
    """Judge Document

    Args:
        document_id (UUID):
        body (JudgeBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | JudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePostResponseJudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePost
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
    body: JudgeBody,
) -> Response[
    HTTPValidationError
    | JudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePostResponseJudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePost
]:
    """Judge Document

    Args:
        document_id (UUID):
        body (JudgeBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | JudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePostResponseJudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePost]
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
    body: JudgeBody,
) -> (
    HTTPValidationError
    | JudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePostResponseJudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePost
    | None
):
    """Judge Document

    Args:
        document_id (UUID):
        body (JudgeBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | JudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePostResponseJudgeDocumentApiV1LibraryDocumentsDocumentIdJudgePost
    """

    return (
        await asyncio_detailed(
            document_id=document_id,
            client=client,
            body=body,
        )
    ).parsed
