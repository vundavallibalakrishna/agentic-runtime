from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_document_check_api_v1_document_checks_check_id_get_response_get_document_check_api_v1_document_checks_check_id_get import (
    GetDocumentCheckApiV1DocumentChecksCheckIdGetResponseGetDocumentCheckApiV1DocumentChecksCheckIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    check_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/document-checks/{check_id}".format(
            check_id=quote(str(check_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetDocumentCheckApiV1DocumentChecksCheckIdGetResponseGetDocumentCheckApiV1DocumentChecksCheckIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetDocumentCheckApiV1DocumentChecksCheckIdGetResponseGetDocumentCheckApiV1DocumentChecksCheckIdGet.from_dict(
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
    GetDocumentCheckApiV1DocumentChecksCheckIdGetResponseGetDocumentCheckApiV1DocumentChecksCheckIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    check_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetDocumentCheckApiV1DocumentChecksCheckIdGetResponseGetDocumentCheckApiV1DocumentChecksCheckIdGet
    | HTTPValidationError
]:
    """Get Document Check

    Args:
        check_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetDocumentCheckApiV1DocumentChecksCheckIdGetResponseGetDocumentCheckApiV1DocumentChecksCheckIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        check_id=check_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    check_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetDocumentCheckApiV1DocumentChecksCheckIdGetResponseGetDocumentCheckApiV1DocumentChecksCheckIdGet
    | HTTPValidationError
    | None
):
    """Get Document Check

    Args:
        check_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetDocumentCheckApiV1DocumentChecksCheckIdGetResponseGetDocumentCheckApiV1DocumentChecksCheckIdGet | HTTPValidationError
    """

    return sync_detailed(
        check_id=check_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    check_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetDocumentCheckApiV1DocumentChecksCheckIdGetResponseGetDocumentCheckApiV1DocumentChecksCheckIdGet
    | HTTPValidationError
]:
    """Get Document Check

    Args:
        check_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetDocumentCheckApiV1DocumentChecksCheckIdGetResponseGetDocumentCheckApiV1DocumentChecksCheckIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        check_id=check_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    check_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetDocumentCheckApiV1DocumentChecksCheckIdGetResponseGetDocumentCheckApiV1DocumentChecksCheckIdGet
    | HTTPValidationError
    | None
):
    """Get Document Check

    Args:
        check_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetDocumentCheckApiV1DocumentChecksCheckIdGetResponseGetDocumentCheckApiV1DocumentChecksCheckIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            check_id=check_id,
            client=client,
        )
    ).parsed
