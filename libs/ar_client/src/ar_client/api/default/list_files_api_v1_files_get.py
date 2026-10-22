from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_files_api_v1_files_get_response_list_files_api_v1_files_get import (
    ListFilesApiV1FilesGetResponseListFilesApiV1FilesGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    *,
    conversation_id: None | Unset | UUID = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_conversation_id: None | str | Unset
    if isinstance(conversation_id, Unset):
        json_conversation_id = UNSET
    elif isinstance(conversation_id, UUID):
        json_conversation_id = str(conversation_id)
    else:
        json_conversation_id = conversation_id
    params["conversationId"] = json_conversation_id

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/files",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ListFilesApiV1FilesGetResponseListFilesApiV1FilesGet | None:
    if response.status_code == 200:
        response_200 = ListFilesApiV1FilesGetResponseListFilesApiV1FilesGet.from_dict(
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
) -> Response[HTTPValidationError | ListFilesApiV1FilesGetResponseListFilesApiV1FilesGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    conversation_id: None | Unset | UUID = UNSET,
) -> Response[HTTPValidationError | ListFilesApiV1FilesGetResponseListFilesApiV1FilesGet]:
    """List Files

    Args:
        conversation_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListFilesApiV1FilesGetResponseListFilesApiV1FilesGet]
    """

    kwargs = _get_kwargs(
        conversation_id=conversation_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    conversation_id: None | Unset | UUID = UNSET,
) -> HTTPValidationError | ListFilesApiV1FilesGetResponseListFilesApiV1FilesGet | None:
    """List Files

    Args:
        conversation_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListFilesApiV1FilesGetResponseListFilesApiV1FilesGet
    """

    return sync_detailed(
        client=client,
        conversation_id=conversation_id,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    conversation_id: None | Unset | UUID = UNSET,
) -> Response[HTTPValidationError | ListFilesApiV1FilesGetResponseListFilesApiV1FilesGet]:
    """List Files

    Args:
        conversation_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListFilesApiV1FilesGetResponseListFilesApiV1FilesGet]
    """

    kwargs = _get_kwargs(
        conversation_id=conversation_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    conversation_id: None | Unset | UUID = UNSET,
) -> HTTPValidationError | ListFilesApiV1FilesGetResponseListFilesApiV1FilesGet | None:
    """List Files

    Args:
        conversation_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListFilesApiV1FilesGetResponseListFilesApiV1FilesGet
    """

    return (
        await asyncio_detailed(
            client=client,
            conversation_id=conversation_id,
        )
    ).parsed
