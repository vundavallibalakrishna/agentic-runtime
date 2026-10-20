from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_tokens_api_v1_scim_tokens_get_response_list_tokens_api_v1_scim_tokens_get import ListTokensApiV1ScimTokensGetResponseListTokensApiV1ScimTokensGet
from typing import cast



def _get_kwargs(
    
) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/scim-tokens",
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> ListTokensApiV1ScimTokensGetResponseListTokensApiV1ScimTokensGet | None:
    if response.status_code == 200:
        response_200 = ListTokensApiV1ScimTokensGetResponseListTokensApiV1ScimTokensGet.from_dict(response.json())



        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[ListTokensApiV1ScimTokensGetResponseListTokensApiV1ScimTokensGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,

) -> Response[ListTokensApiV1ScimTokensGetResponseListTokensApiV1ScimTokensGet]:
    """ List Tokens

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListTokensApiV1ScimTokensGetResponseListTokensApiV1ScimTokensGet]
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

) -> ListTokensApiV1ScimTokensGetResponseListTokensApiV1ScimTokensGet | None:
    """ List Tokens

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListTokensApiV1ScimTokensGetResponseListTokensApiV1ScimTokensGet
     """


    return sync_detailed(
        client=client,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,

) -> Response[ListTokensApiV1ScimTokensGetResponseListTokensApiV1ScimTokensGet]:
    """ List Tokens

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListTokensApiV1ScimTokensGetResponseListTokensApiV1ScimTokensGet]
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

) -> ListTokensApiV1ScimTokensGetResponseListTokensApiV1ScimTokensGet | None:
    """ List Tokens

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListTokensApiV1ScimTokensGetResponseListTokensApiV1ScimTokensGet
     """


    return (await asyncio_detailed(
        client=client,

    )).parsed
