from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.decide_body import DecideBody
from ...models.decide_document_rewrite_api_v1_document_rewrites_rewrite_id_decide_post_response_decide_document_rewrite_api_v1_document_rewrites_rewrite_id_decide_post import (
    DecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePostResponseDecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    rewrite_id: UUID,
    *,
    body: DecideBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/document-rewrites/{rewrite_id}:decide".format(
            rewrite_id=quote(str(rewrite_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePostResponseDecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePostResponseDecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePost.from_dict(
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
    DecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePostResponseDecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    rewrite_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DecideBody,
) -> Response[
    DecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePostResponseDecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePost
    | HTTPValidationError
]:
    """Decide Document Rewrite

    Args:
        rewrite_id (UUID):
        body (DecideBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePostResponseDecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        rewrite_id=rewrite_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    rewrite_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DecideBody,
) -> (
    DecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePostResponseDecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePost
    | HTTPValidationError
    | None
):
    """Decide Document Rewrite

    Args:
        rewrite_id (UUID):
        body (DecideBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePostResponseDecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePost | HTTPValidationError
    """

    return sync_detailed(
        rewrite_id=rewrite_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    rewrite_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DecideBody,
) -> Response[
    DecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePostResponseDecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePost
    | HTTPValidationError
]:
    """Decide Document Rewrite

    Args:
        rewrite_id (UUID):
        body (DecideBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePostResponseDecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        rewrite_id=rewrite_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    rewrite_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DecideBody,
) -> (
    DecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePostResponseDecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePost
    | HTTPValidationError
    | None
):
    """Decide Document Rewrite

    Args:
        rewrite_id (UUID):
        body (DecideBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePostResponseDecideDocumentRewriteApiV1DocumentRewritesRewriteIdDecidePost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            rewrite_id=rewrite_id,
            client=client,
            body=body,
        )
    ).parsed
