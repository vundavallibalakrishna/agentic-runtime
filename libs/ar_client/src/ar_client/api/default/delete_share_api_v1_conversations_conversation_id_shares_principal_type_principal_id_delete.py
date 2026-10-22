from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_share_api_v1_conversations_conversation_id_shares_principal_type_principal_id_delete_response_delete_share_api_v1_conversations_conversation_id_shares_principal_type_principal_id_delete import (
    DeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDeleteResponseDeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    conversation_id: UUID,
    principal_type: str,
    principal_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/conversations/{conversation_id}/shares/{principal_type}/{principal_id}".format(
            conversation_id=quote(str(conversation_id), safe=""),
            principal_type=quote(str(principal_type), safe=""),
            principal_id=quote(str(principal_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDeleteResponseDeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDeleteResponseDeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDelete.from_dict(
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
    DeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDeleteResponseDeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDelete
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
    principal_type: str,
    principal_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDeleteResponseDeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDelete
    | HTTPValidationError
]:
    """Delete Share

    Args:
        conversation_id (UUID):
        principal_type (str):
        principal_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDeleteResponseDeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        conversation_id=conversation_id,
        principal_type=principal_type,
        principal_id=principal_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    conversation_id: UUID,
    principal_type: str,
    principal_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDeleteResponseDeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDelete
    | HTTPValidationError
    | None
):
    """Delete Share

    Args:
        conversation_id (UUID):
        principal_type (str):
        principal_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDeleteResponseDeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDelete | HTTPValidationError
    """

    return sync_detailed(
        conversation_id=conversation_id,
        principal_type=principal_type,
        principal_id=principal_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    conversation_id: UUID,
    principal_type: str,
    principal_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDeleteResponseDeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDelete
    | HTTPValidationError
]:
    """Delete Share

    Args:
        conversation_id (UUID):
        principal_type (str):
        principal_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDeleteResponseDeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        conversation_id=conversation_id,
        principal_type=principal_type,
        principal_id=principal_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    conversation_id: UUID,
    principal_type: str,
    principal_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDeleteResponseDeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDelete
    | HTTPValidationError
    | None
):
    """Delete Share

    Args:
        conversation_id (UUID):
        principal_type (str):
        principal_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDeleteResponseDeleteShareApiV1ConversationsConversationIdSharesPrincipalTypePrincipalIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            conversation_id=conversation_id,
            principal_type=principal_type,
            principal_id=principal_id,
            client=client,
        )
    ).parsed
