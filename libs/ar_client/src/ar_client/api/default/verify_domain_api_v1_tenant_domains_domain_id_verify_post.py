from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.verify_domain_api_v1_tenant_domains_domain_id_verify_post_response_verify_domain_api_v1_tenant_domains_domain_id_verify_post import VerifyDomainApiV1TenantDomainsDomainIdVerifyPostResponseVerifyDomainApiV1TenantDomainsDomainIdVerifyPost
from typing import cast
from uuid import UUID



def _get_kwargs(
    domain_id: UUID,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/tenant/domains/{domain_id}:verify".format(domain_id=quote(str(domain_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | VerifyDomainApiV1TenantDomainsDomainIdVerifyPostResponseVerifyDomainApiV1TenantDomainsDomainIdVerifyPost | None:
    if response.status_code == 200:
        response_200 = VerifyDomainApiV1TenantDomainsDomainIdVerifyPostResponseVerifyDomainApiV1TenantDomainsDomainIdVerifyPost.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | VerifyDomainApiV1TenantDomainsDomainIdVerifyPostResponseVerifyDomainApiV1TenantDomainsDomainIdVerifyPost]:
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

) -> Response[HTTPValidationError | VerifyDomainApiV1TenantDomainsDomainIdVerifyPostResponseVerifyDomainApiV1TenantDomainsDomainIdVerifyPost]:
    """ Verify Domain

    Args:
        domain_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | VerifyDomainApiV1TenantDomainsDomainIdVerifyPostResponseVerifyDomainApiV1TenantDomainsDomainIdVerifyPost]
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

) -> HTTPValidationError | VerifyDomainApiV1TenantDomainsDomainIdVerifyPostResponseVerifyDomainApiV1TenantDomainsDomainIdVerifyPost | None:
    """ Verify Domain

    Args:
        domain_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | VerifyDomainApiV1TenantDomainsDomainIdVerifyPostResponseVerifyDomainApiV1TenantDomainsDomainIdVerifyPost
     """


    return sync_detailed(
        domain_id=domain_id,
client=client,

    ).parsed

async def asyncio_detailed(
    domain_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[HTTPValidationError | VerifyDomainApiV1TenantDomainsDomainIdVerifyPostResponseVerifyDomainApiV1TenantDomainsDomainIdVerifyPost]:
    """ Verify Domain

    Args:
        domain_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | VerifyDomainApiV1TenantDomainsDomainIdVerifyPostResponseVerifyDomainApiV1TenantDomainsDomainIdVerifyPost]
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

) -> HTTPValidationError | VerifyDomainApiV1TenantDomainsDomainIdVerifyPostResponseVerifyDomainApiV1TenantDomainsDomainIdVerifyPost | None:
    """ Verify Domain

    Args:
        domain_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | VerifyDomainApiV1TenantDomainsDomainIdVerifyPostResponseVerifyDomainApiV1TenantDomainsDomainIdVerifyPost
     """


    return (await asyncio_detailed(
        domain_id=domain_id,
client=client,

    )).parsed
