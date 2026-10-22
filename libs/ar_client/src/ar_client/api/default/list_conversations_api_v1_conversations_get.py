from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_conversations_api_v1_conversations_get_response_list_conversations_api_v1_conversations_get import (
    ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet,
)
from ...types import UNSET, Unset
from typing import cast


def _get_kwargs(
    *,
    include_previews: bool | Unset = False,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["includePreviews"] = include_previews

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/conversations",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet
    | None
):
    if response.status_code == 200:
        response_200 = ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet.from_dict(
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
    | ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet
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
    include_previews: bool | Unset = False,
) -> Response[
    HTTPValidationError
    | ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet
]:
    """List Conversations

    Args:
        include_previews (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet]
    """

    kwargs = _get_kwargs(
        include_previews=include_previews,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    include_previews: bool | Unset = False,
) -> (
    HTTPValidationError
    | ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet
    | None
):
    """List Conversations

    Args:
        include_previews (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet
    """

    return sync_detailed(
        client=client,
        include_previews=include_previews,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    include_previews: bool | Unset = False,
) -> Response[
    HTTPValidationError
    | ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet
]:
    """List Conversations

    Args:
        include_previews (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet]
    """

    kwargs = _get_kwargs(
        include_previews=include_previews,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    include_previews: bool | Unset = False,
) -> (
    HTTPValidationError
    | ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet
    | None
):
    """List Conversations

    Args:
        include_previews (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet
    """

    return (
        await asyncio_detailed(
            client=client,
            include_previews=include_previews,
        )
    ).parsed
