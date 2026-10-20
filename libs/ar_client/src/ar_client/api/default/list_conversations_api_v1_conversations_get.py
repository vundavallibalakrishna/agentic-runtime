from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_conversations_api_v1_conversations_get_response_list_conversations_api_v1_conversations_get import ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet
from typing import cast



def _get_kwargs(
    
) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/conversations",
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet | None:
    if response.status_code == 200:
        response_200 = ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet.from_dict(response.json())



        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,

) -> Response[ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet]:
    """ List Conversations

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet]
     """


    kwargs = _get_kwargs(
        
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    *,
    client: AuthenticatedClient | Client,

) -> ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet | None:
    """ List Conversations

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet
     """


    return sync_detailed(
        client=client,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,

) -> Response[ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet]:
    """ List Conversations

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet]
     """


    kwargs = _get_kwargs(
        
    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    *,
    client: AuthenticatedClient | Client,

) -> ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet | None:
    """ List Conversations

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListConversationsApiV1ConversationsGetResponseListConversationsApiV1ConversationsGet
     """


    return (await asyncio_detailed(
        client=client,

    )).parsed
