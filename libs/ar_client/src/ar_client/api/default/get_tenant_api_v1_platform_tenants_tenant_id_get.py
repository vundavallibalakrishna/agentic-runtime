from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_tenant_api_v1_platform_tenants_tenant_id_get_response_get_tenant_api_v1_platform_tenants_tenant_id_get import GetTenantApiV1PlatformTenantsTenantIdGetResponseGetTenantApiV1PlatformTenantsTenantIdGet
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID



def _get_kwargs(
    tenant_id: UUID,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/platform/tenants/{tenant_id}".format(tenant_id=quote(str(tenant_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> GetTenantApiV1PlatformTenantsTenantIdGetResponseGetTenantApiV1PlatformTenantsTenantIdGet | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = GetTenantApiV1PlatformTenantsTenantIdGetResponseGetTenantApiV1PlatformTenantsTenantIdGet.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[GetTenantApiV1PlatformTenantsTenantIdGetResponseGetTenantApiV1PlatformTenantsTenantIdGet | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    tenant_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[GetTenantApiV1PlatformTenantsTenantIdGetResponseGetTenantApiV1PlatformTenantsTenantIdGet | HTTPValidationError]:
    """ Get Tenant

    Args:
        tenant_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetTenantApiV1PlatformTenantsTenantIdGetResponseGetTenantApiV1PlatformTenantsTenantIdGet | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        tenant_id=tenant_id,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    tenant_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> GetTenantApiV1PlatformTenantsTenantIdGetResponseGetTenantApiV1PlatformTenantsTenantIdGet | HTTPValidationError | None:
    """ Get Tenant

    Args:
        tenant_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetTenantApiV1PlatformTenantsTenantIdGetResponseGetTenantApiV1PlatformTenantsTenantIdGet | HTTPValidationError
     """


    return sync_detailed(
        tenant_id=tenant_id,
client=client,

    ).parsed

async def asyncio_detailed(
    tenant_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[GetTenantApiV1PlatformTenantsTenantIdGetResponseGetTenantApiV1PlatformTenantsTenantIdGet | HTTPValidationError]:
    """ Get Tenant

    Args:
        tenant_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetTenantApiV1PlatformTenantsTenantIdGetResponseGetTenantApiV1PlatformTenantsTenantIdGet | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        tenant_id=tenant_id,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    tenant_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> GetTenantApiV1PlatformTenantsTenantIdGetResponseGetTenantApiV1PlatformTenantsTenantIdGet | HTTPValidationError | None:
    """ Get Tenant

    Args:
        tenant_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetTenantApiV1PlatformTenantsTenantIdGetResponseGetTenantApiV1PlatformTenantsTenantIdGet | HTTPValidationError
     """


    return (await asyncio_detailed(
        tenant_id=tenant_id,
client=client,

    )).parsed
