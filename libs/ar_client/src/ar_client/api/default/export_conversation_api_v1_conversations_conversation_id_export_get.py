from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.export_conversation_api_v1_conversations_conversation_id_export_get_response_export_conversation_api_v1_conversations_conversation_id_export_get import ExportConversationApiV1ConversationsConversationIdExportGetResponseExportConversationApiV1ConversationsConversationIdExportGet
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID



def _get_kwargs(
    conversation_id: UUID,
    *,
    format_: str | Unset = 'markdown',

) -> dict[str, Any]:
    

    

    params: dict[str, Any] = {}

    params["format"] = format_


    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}


    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/conversations/{conversation_id}/export".format(conversation_id=quote(str(conversation_id), safe=""),),
        "params": params,
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> ExportConversationApiV1ConversationsConversationIdExportGetResponseExportConversationApiV1ConversationsConversationIdExportGet | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = ExportConversationApiV1ConversationsConversationIdExportGetResponseExportConversationApiV1ConversationsConversationIdExportGet.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[ExportConversationApiV1ConversationsConversationIdExportGetResponseExportConversationApiV1ConversationsConversationIdExportGet | HTTPValidationError]:
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
    format_: str | Unset = 'markdown',

) -> Response[ExportConversationApiV1ConversationsConversationIdExportGetResponseExportConversationApiV1ConversationsConversationIdExportGet | HTTPValidationError]:
    """ Export Conversation

    Args:
        conversation_id (UUID):
        format_ (str | Unset):  Default: 'markdown'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ExportConversationApiV1ConversationsConversationIdExportGetResponseExportConversationApiV1ConversationsConversationIdExportGet | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        conversation_id=conversation_id,
format_=format_,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    conversation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    format_: str | Unset = 'markdown',

) -> ExportConversationApiV1ConversationsConversationIdExportGetResponseExportConversationApiV1ConversationsConversationIdExportGet | HTTPValidationError | None:
    """ Export Conversation

    Args:
        conversation_id (UUID):
        format_ (str | Unset):  Default: 'markdown'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ExportConversationApiV1ConversationsConversationIdExportGetResponseExportConversationApiV1ConversationsConversationIdExportGet | HTTPValidationError
     """


    return sync_detailed(
        conversation_id=conversation_id,
client=client,
format_=format_,

    ).parsed

async def asyncio_detailed(
    conversation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    format_: str | Unset = 'markdown',

) -> Response[ExportConversationApiV1ConversationsConversationIdExportGetResponseExportConversationApiV1ConversationsConversationIdExportGet | HTTPValidationError]:
    """ Export Conversation

    Args:
        conversation_id (UUID):
        format_ (str | Unset):  Default: 'markdown'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ExportConversationApiV1ConversationsConversationIdExportGetResponseExportConversationApiV1ConversationsConversationIdExportGet | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        conversation_id=conversation_id,
format_=format_,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    conversation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    format_: str | Unset = 'markdown',

) -> ExportConversationApiV1ConversationsConversationIdExportGetResponseExportConversationApiV1ConversationsConversationIdExportGet | HTTPValidationError | None:
    """ Export Conversation

    Args:
        conversation_id (UUID):
        format_ (str | Unset):  Default: 'markdown'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ExportConversationApiV1ConversationsConversationIdExportGetResponseExportConversationApiV1ConversationsConversationIdExportGet | HTTPValidationError
     """


    return (await asyncio_detailed(
        conversation_id=conversation_id,
client=client,
format_=format_,

    )).parsed
