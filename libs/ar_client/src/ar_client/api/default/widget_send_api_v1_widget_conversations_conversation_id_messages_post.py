from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.widget_message_body import WidgetMessageBody
from ...models.widget_send_api_v1_widget_conversations_conversation_id_messages_post_response_widget_send_api_v1_widget_conversations_conversation_id_messages_post import (
    WidgetSendApiV1WidgetConversationsConversationIdMessagesPostResponseWidgetSendApiV1WidgetConversationsConversationIdMessagesPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    conversation_id: UUID,
    *,
    body: WidgetMessageBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/widget/conversations/{conversation_id}/messages".format(
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
    HTTPValidationError
    | WidgetSendApiV1WidgetConversationsConversationIdMessagesPostResponseWidgetSendApiV1WidgetConversationsConversationIdMessagesPost
    | None
):
    if response.status_code == 202:
        response_202 = WidgetSendApiV1WidgetConversationsConversationIdMessagesPostResponseWidgetSendApiV1WidgetConversationsConversationIdMessagesPost.from_dict(
            response.json()
        )

        return response_202

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
    | WidgetSendApiV1WidgetConversationsConversationIdMessagesPostResponseWidgetSendApiV1WidgetConversationsConversationIdMessagesPost
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
    body: WidgetMessageBody,
) -> Response[
    HTTPValidationError
    | WidgetSendApiV1WidgetConversationsConversationIdMessagesPostResponseWidgetSendApiV1WidgetConversationsConversationIdMessagesPost
]:
    """Widget Send

    Args:
        conversation_id (UUID):
        body (WidgetMessageBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | WidgetSendApiV1WidgetConversationsConversationIdMessagesPostResponseWidgetSendApiV1WidgetConversationsConversationIdMessagesPost]
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
    body: WidgetMessageBody,
) -> (
    HTTPValidationError
    | WidgetSendApiV1WidgetConversationsConversationIdMessagesPostResponseWidgetSendApiV1WidgetConversationsConversationIdMessagesPost
    | None
):
    """Widget Send

    Args:
        conversation_id (UUID):
        body (WidgetMessageBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | WidgetSendApiV1WidgetConversationsConversationIdMessagesPostResponseWidgetSendApiV1WidgetConversationsConversationIdMessagesPost
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
    body: WidgetMessageBody,
) -> Response[
    HTTPValidationError
    | WidgetSendApiV1WidgetConversationsConversationIdMessagesPostResponseWidgetSendApiV1WidgetConversationsConversationIdMessagesPost
]:
    """Widget Send

    Args:
        conversation_id (UUID):
        body (WidgetMessageBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | WidgetSendApiV1WidgetConversationsConversationIdMessagesPostResponseWidgetSendApiV1WidgetConversationsConversationIdMessagesPost]
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
    body: WidgetMessageBody,
) -> (
    HTTPValidationError
    | WidgetSendApiV1WidgetConversationsConversationIdMessagesPostResponseWidgetSendApiV1WidgetConversationsConversationIdMessagesPost
    | None
):
    """Widget Send

    Args:
        conversation_id (UUID):
        body (WidgetMessageBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | WidgetSendApiV1WidgetConversationsConversationIdMessagesPostResponseWidgetSendApiV1WidgetConversationsConversationIdMessagesPost
    """

    return (
        await asyncio_detailed(
            conversation_id=conversation_id,
            client=client,
            body=body,
        )
    ).parsed
