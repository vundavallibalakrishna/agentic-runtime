from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_document_comparison_api_v1_document_comparisons_comparison_id_get_response_get_document_comparison_api_v1_document_comparisons_comparison_id_get import (
    GetDocumentComparisonApiV1DocumentComparisonsComparisonIdGetResponseGetDocumentComparisonApiV1DocumentComparisonsComparisonIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    comparison_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/document-comparisons/{comparison_id}".format(
            comparison_id=quote(str(comparison_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetDocumentComparisonApiV1DocumentComparisonsComparisonIdGetResponseGetDocumentComparisonApiV1DocumentComparisonsComparisonIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetDocumentComparisonApiV1DocumentComparisonsComparisonIdGetResponseGetDocumentComparisonApiV1DocumentComparisonsComparisonIdGet.from_dict(
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
    GetDocumentComparisonApiV1DocumentComparisonsComparisonIdGetResponseGetDocumentComparisonApiV1DocumentComparisonsComparisonIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    comparison_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetDocumentComparisonApiV1DocumentComparisonsComparisonIdGetResponseGetDocumentComparisonApiV1DocumentComparisonsComparisonIdGet
    | HTTPValidationError
]:
    """Get Document Comparison

    Args:
        comparison_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetDocumentComparisonApiV1DocumentComparisonsComparisonIdGetResponseGetDocumentComparisonApiV1DocumentComparisonsComparisonIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        comparison_id=comparison_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    comparison_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetDocumentComparisonApiV1DocumentComparisonsComparisonIdGetResponseGetDocumentComparisonApiV1DocumentComparisonsComparisonIdGet
    | HTTPValidationError
    | None
):
    """Get Document Comparison

    Args:
        comparison_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetDocumentComparisonApiV1DocumentComparisonsComparisonIdGetResponseGetDocumentComparisonApiV1DocumentComparisonsComparisonIdGet | HTTPValidationError
    """

    return sync_detailed(
        comparison_id=comparison_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    comparison_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetDocumentComparisonApiV1DocumentComparisonsComparisonIdGetResponseGetDocumentComparisonApiV1DocumentComparisonsComparisonIdGet
    | HTTPValidationError
]:
    """Get Document Comparison

    Args:
        comparison_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetDocumentComparisonApiV1DocumentComparisonsComparisonIdGetResponseGetDocumentComparisonApiV1DocumentComparisonsComparisonIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        comparison_id=comparison_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    comparison_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetDocumentComparisonApiV1DocumentComparisonsComparisonIdGetResponseGetDocumentComparisonApiV1DocumentComparisonsComparisonIdGet
    | HTTPValidationError
    | None
):
    """Get Document Comparison

    Args:
        comparison_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetDocumentComparisonApiV1DocumentComparisonsComparisonIdGetResponseGetDocumentComparisonApiV1DocumentComparisonsComparisonIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            comparison_id=comparison_id,
            client=client,
        )
    ).parsed
