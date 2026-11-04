from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_library_documents_api_v1_library_documents_get_response_list_library_documents_api_v1_library_documents_get import (
    ListLibraryDocumentsApiV1LibraryDocumentsGetResponseListLibraryDocumentsApiV1LibraryDocumentsGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/library-documents",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ListLibraryDocumentsApiV1LibraryDocumentsGetResponseListLibraryDocumentsApiV1LibraryDocumentsGet
    | None
):
    if response.status_code == 200:
        response_200 = ListLibraryDocumentsApiV1LibraryDocumentsGetResponseListLibraryDocumentsApiV1LibraryDocumentsGet.from_dict(
            response.json()
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    ListLibraryDocumentsApiV1LibraryDocumentsGetResponseListLibraryDocumentsApiV1LibraryDocumentsGet
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ListLibraryDocumentsApiV1LibraryDocumentsGetResponseListLibraryDocumentsApiV1LibraryDocumentsGet
]:
    """List Library Documents

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListLibraryDocumentsApiV1LibraryDocumentsGetResponseListLibraryDocumentsApiV1LibraryDocumentsGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> (
    ListLibraryDocumentsApiV1LibraryDocumentsGetResponseListLibraryDocumentsApiV1LibraryDocumentsGet
    | None
):
    """List Library Documents

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListLibraryDocumentsApiV1LibraryDocumentsGetResponseListLibraryDocumentsApiV1LibraryDocumentsGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ListLibraryDocumentsApiV1LibraryDocumentsGetResponseListLibraryDocumentsApiV1LibraryDocumentsGet
]:
    """List Library Documents

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListLibraryDocumentsApiV1LibraryDocumentsGetResponseListLibraryDocumentsApiV1LibraryDocumentsGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> (
    ListLibraryDocumentsApiV1LibraryDocumentsGetResponseListLibraryDocumentsApiV1LibraryDocumentsGet
    | None
):
    """List Library Documents

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListLibraryDocumentsApiV1LibraryDocumentsGetResponseListLibraryDocumentsApiV1LibraryDocumentsGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
