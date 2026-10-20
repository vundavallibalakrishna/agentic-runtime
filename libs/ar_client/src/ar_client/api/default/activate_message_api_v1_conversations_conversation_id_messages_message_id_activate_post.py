from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.activate_message_api_v1_conversations_conversation_id_messages_message_id_activate_post_response_activate_message_api_v1_conversations_conversation_id_messages_message_id_activate_post import ActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePostResponseActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePost
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID



def _get_kwargs(
    conversation_id: UUID,
    message_id: UUID,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/conversations/{conversation_id}/messages/{message_id}:activate".format(conversation_id=quote(str(conversation_id), safe=""),message_id=quote(str(message_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> ActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePostResponseActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePost | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = ActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePostResponseActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePost.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[ActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePostResponseActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePost | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    conversation_id: UUID,
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[ActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePostResponseActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePost | HTTPValidationError]:
    """ Activate Message

    Args:
        conversation_id (UUID):
        message_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePostResponseActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePost | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        conversation_id=conversation_id,
message_id=message_id,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    conversation_id: UUID,
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> ActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePostResponseActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePost | HTTPValidationError | None:
    """ Activate Message

    Args:
        conversation_id (UUID):
        message_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePostResponseActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePost | HTTPValidationError
     """


    return sync_detailed(
        conversation_id=conversation_id,
message_id=message_id,
client=client,

    ).parsed

async def asyncio_detailed(
    conversation_id: UUID,
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[ActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePostResponseActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePost | HTTPValidationError]:
    """ Activate Message

    Args:
        conversation_id (UUID):
        message_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePostResponseActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePost | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        conversation_id=conversation_id,
message_id=message_id,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    conversation_id: UUID,
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> ActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePostResponseActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePost | HTTPValidationError | None:
    """ Activate Message

    Args:
        conversation_id (UUID):
        message_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePostResponseActivateMessageApiV1ConversationsConversationIdMessagesMessageIdActivatePost | HTTPValidationError
     """


    return (await asyncio_detailed(
        conversation_id=conversation_id,
message_id=message_id,
client=client,

    )).parsed
