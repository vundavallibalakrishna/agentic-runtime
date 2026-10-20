from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_domain_api_v1_tenant_domains_domain_id_delete_response_delete_domain_api_v1_tenant_domains_domain_id_delete import DeleteDomainApiV1TenantDomainsDomainIdDeleteResponseDeleteDomainApiV1TenantDomainsDomainIdDelete
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID



def _get_kwargs(
    domain_id: UUID,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/tenant/domains/{domain_id}".format(domain_id=quote(str(domain_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> DeleteDomainApiV1TenantDomainsDomainIdDeleteResponseDeleteDomainApiV1TenantDomainsDomainIdDelete | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = DeleteDomainApiV1TenantDomainsDomainIdDeleteResponseDeleteDomainApiV1TenantDomainsDomainIdDelete.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[DeleteDomainApiV1TenantDomainsDomainIdDeleteResponseDeleteDomainApiV1TenantDomainsDomainIdDelete | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    domain_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[DeleteDomainApiV1TenantDomainsDomainIdDeleteResponseDeleteDomainApiV1TenantDomainsDomainIdDelete | HTTPValidationError]:
    """ Delete Domain

    Args:
        domain_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteDomainApiV1TenantDomainsDomainIdDeleteResponseDeleteDomainApiV1TenantDomainsDomainIdDelete | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        domain_id=domain_id,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    domain_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeleteDomainApiV1TenantDomainsDomainIdDeleteResponseDeleteDomainApiV1TenantDomainsDomainIdDelete | HTTPValidationError | None:
    """ Delete Domain

    Args:
        domain_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteDomainApiV1TenantDomainsDomainIdDeleteResponseDeleteDomainApiV1TenantDomainsDomainIdDelete | HTTPValidationError
     """


    return sync_detailed(
        domain_id=domain_id,
client=client,

    ).parsed

async def asyncio_detailed(
    domain_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[DeleteDomainApiV1TenantDomainsDomainIdDeleteResponseDeleteDomainApiV1TenantDomainsDomainIdDelete | HTTPValidationError]:
    """ Delete Domain

    Args:
        domain_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteDomainApiV1TenantDomainsDomainIdDeleteResponseDeleteDomainApiV1TenantDomainsDomainIdDelete | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        domain_id=domain_id,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    domain_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeleteDomainApiV1TenantDomainsDomainIdDeleteResponseDeleteDomainApiV1TenantDomainsDomainIdDelete | HTTPValidationError | None:
    """ Delete Domain

    Args:
        domain_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteDomainApiV1TenantDomainsDomainIdDeleteResponseDeleteDomainApiV1TenantDomainsDomainIdDelete | HTTPValidationError
     """


    return (await asyncio_detailed(
        domain_id=domain_id,
client=client,

    )).parsed
