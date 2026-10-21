from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.platform_providers_api_v1_platform_model_providers_get_response_platform_providers_api_v1_platform_model_providers_get import PlatformProvidersApiV1PlatformModelProvidersGetResponsePlatformProvidersApiV1PlatformModelProvidersGet
from typing import cast



def _get_kwargs(
    
) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/platform/model-providers",
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> PlatformProvidersApiV1PlatformModelProvidersGetResponsePlatformProvidersApiV1PlatformModelProvidersGet | None:
    if response.status_code == 200:
        response_200 = PlatformProvidersApiV1PlatformModelProvidersGetResponsePlatformProvidersApiV1PlatformModelProvidersGet.from_dict(response.json())



        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[PlatformProvidersApiV1PlatformModelProvidersGetResponsePlatformProvidersApiV1PlatformModelProvidersGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,

) -> Response[PlatformProvidersApiV1PlatformModelProvidersGetResponsePlatformProvidersApiV1PlatformModelProvidersGet]:
    """ Platform Providers

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PlatformProvidersApiV1PlatformModelProvidersGetResponsePlatformProvidersApiV1PlatformModelProvidersGet]
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

) -> PlatformProvidersApiV1PlatformModelProvidersGetResponsePlatformProvidersApiV1PlatformModelProvidersGet | None:
    """ Platform Providers

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PlatformProvidersApiV1PlatformModelProvidersGetResponsePlatformProvidersApiV1PlatformModelProvidersGet
     """


    return sync_detailed(
        client=client,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,

) -> Response[PlatformProvidersApiV1PlatformModelProvidersGetResponsePlatformProvidersApiV1PlatformModelProvidersGet]:
    """ Platform Providers

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PlatformProvidersApiV1PlatformModelProvidersGetResponsePlatformProvidersApiV1PlatformModelProvidersGet]
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

) -> PlatformProvidersApiV1PlatformModelProvidersGetResponsePlatformProvidersApiV1PlatformModelProvidersGet | None:
    """ Platform Providers

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PlatformProvidersApiV1PlatformModelProvidersGetResponsePlatformProvidersApiV1PlatformModelProvidersGet
     """


    return (await asyncio_detailed(
        client=client,

    )).parsed
