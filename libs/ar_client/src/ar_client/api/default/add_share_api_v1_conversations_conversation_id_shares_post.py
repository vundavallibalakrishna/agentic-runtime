from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.add_share_api_v1_conversations_conversation_id_shares_post_response_add_share_api_v1_conversations_conversation_id_shares_post import (
    AddShareApiV1ConversationsConversationIdSharesPostResponseAddShareApiV1ConversationsConversationIdSharesPost,
)
from ...models.http_validation_error import HTTPValidationError
from ...models.share_body import ShareBody
from typing import cast
from uuid import UUID


def _get_kwargs(
    conversation_id: UUID,
    *,
    body: ShareBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/conversations/{conversation_id}/shares".format(
            conversation_id=quote(str(conversation_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    AddShareApiV1ConversationsConversationIdSharesPostResponseAddShareApiV1ConversationsConversationIdSharesPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = AddShareApiV1ConversationsConversationIdSharesPostResponseAddShareApiV1ConversationsConversationIdSharesPost.from_dict(
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
    AddShareApiV1ConversationsConversationIdSharesPostResponseAddShareApiV1ConversationsConversationIdSharesPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    conversation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ShareBody,
) -> Response[
    AddShareApiV1ConversationsConversationIdSharesPostResponseAddShareApiV1ConversationsConversationIdSharesPost
    | HTTPValidationError
]:
    """Add Share

    Args:
        conversation_id (UUID):
        body (ShareBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AddShareApiV1ConversationsConversationIdSharesPostResponseAddShareApiV1ConversationsConversationIdSharesPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        conversation_id=conversation_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    conversation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ShareBody,
) -> (
    AddShareApiV1ConversationsConversationIdSharesPostResponseAddShareApiV1ConversationsConversationIdSharesPost
    | HTTPValidationError
    | None
):
    """Add Share

    Args:
        conversation_id (UUID):
        body (ShareBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AddShareApiV1ConversationsConversationIdSharesPostResponseAddShareApiV1ConversationsConversationIdSharesPost | HTTPValidationError
    """

    return sync_detailed(
        conversation_id=conversation_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    conversation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ShareBody,
) -> Response[
    AddShareApiV1ConversationsConversationIdSharesPostResponseAddShareApiV1ConversationsConversationIdSharesPost
    | HTTPValidationError
]:
    """Add Share

    Args:
        conversation_id (UUID):
        body (ShareBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AddShareApiV1ConversationsConversationIdSharesPostResponseAddShareApiV1ConversationsConversationIdSharesPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        conversation_id=conversation_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    conversation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ShareBody,
) -> (
    AddShareApiV1ConversationsConversationIdSharesPostResponseAddShareApiV1ConversationsConversationIdSharesPost
    | HTTPValidationError
    | None
):
    """Add Share

    Args:
        conversation_id (UUID):
        body (ShareBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AddShareApiV1ConversationsConversationIdSharesPostResponseAddShareApiV1ConversationsConversationIdSharesPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            conversation_id=conversation_id,
            client=client,
            body=body,
        )
    ).parsed
