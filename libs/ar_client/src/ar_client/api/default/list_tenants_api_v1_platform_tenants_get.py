from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_tenants_api_v1_platform_tenants_get_response_list_tenants_api_v1_platform_tenants_get import ListTenantsApiV1PlatformTenantsGetResponseListTenantsApiV1PlatformTenantsGet
from typing import cast



def _get_kwargs(
    
) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/platform/tenants",
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> ListTenantsApiV1PlatformTenantsGetResponseListTenantsApiV1PlatformTenantsGet | None:
    if response.status_code == 200:
        response_200 = ListTenantsApiV1PlatformTenantsGetResponseListTenantsApiV1PlatformTenantsGet.from_dict(response.json())



        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[ListTenantsApiV1PlatformTenantsGetResponseListTenantsApiV1PlatformTenantsGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,

) -> Response[ListTenantsApiV1PlatformTenantsGetResponseListTenantsApiV1PlatformTenantsGet]:
    """ List Tenants

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListTenantsApiV1PlatformTenantsGetResponseListTenantsApiV1PlatformTenantsGet]
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

) -> ListTenantsApiV1PlatformTenantsGetResponseListTenantsApiV1PlatformTenantsGet | None:
    """ List Tenants

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListTenantsApiV1PlatformTenantsGetResponseListTenantsApiV1PlatformTenantsGet
     """


    return sync_detailed(
        client=client,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,

) -> Response[ListTenantsApiV1PlatformTenantsGetResponseListTenantsApiV1PlatformTenantsGet]:
    """ List Tenants

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListTenantsApiV1PlatformTenantsGetResponseListTenantsApiV1PlatformTenantsGet]
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

) -> ListTenantsApiV1PlatformTenantsGetResponseListTenantsApiV1PlatformTenantsGet | None:
    """ List Tenants

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListTenantsApiV1PlatformTenantsGetResponseListTenantsApiV1PlatformTenantsGet
     """


    return (await asyncio_detailed(
        client=client,

    )).parsed
