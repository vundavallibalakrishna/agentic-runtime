from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_service_accounts_api_v1_service_accounts_get_response_list_service_accounts_api_v1_service_accounts_get import ListServiceAccountsApiV1ServiceAccountsGetResponseListServiceAccountsApiV1ServiceAccountsGet
from typing import cast



def _get_kwargs(
    
) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/service-accounts",
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> ListServiceAccountsApiV1ServiceAccountsGetResponseListServiceAccountsApiV1ServiceAccountsGet | None:
    if response.status_code == 200:
        response_200 = ListServiceAccountsApiV1ServiceAccountsGetResponseListServiceAccountsApiV1ServiceAccountsGet.from_dict(response.json())



        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[ListServiceAccountsApiV1ServiceAccountsGetResponseListServiceAccountsApiV1ServiceAccountsGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,

) -> Response[ListServiceAccountsApiV1ServiceAccountsGetResponseListServiceAccountsApiV1ServiceAccountsGet]:
    """ List Service Accounts

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListServiceAccountsApiV1ServiceAccountsGetResponseListServiceAccountsApiV1ServiceAccountsGet]
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

) -> ListServiceAccountsApiV1ServiceAccountsGetResponseListServiceAccountsApiV1ServiceAccountsGet | None:
    """ List Service Accounts

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListServiceAccountsApiV1ServiceAccountsGetResponseListServiceAccountsApiV1ServiceAccountsGet
     """


    return sync_detailed(
        client=client,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,

) -> Response[ListServiceAccountsApiV1ServiceAccountsGetResponseListServiceAccountsApiV1ServiceAccountsGet]:
    """ List Service Accounts

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListServiceAccountsApiV1ServiceAccountsGetResponseListServiceAccountsApiV1ServiceAccountsGet]
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

) -> ListServiceAccountsApiV1ServiceAccountsGetResponseListServiceAccountsApiV1ServiceAccountsGet | None:
    """ List Service Accounts

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListServiceAccountsApiV1ServiceAccountsGetResponseListServiceAccountsApiV1ServiceAccountsGet
     """


    return (await asyncio_detailed(
        client=client,

    )).parsed
