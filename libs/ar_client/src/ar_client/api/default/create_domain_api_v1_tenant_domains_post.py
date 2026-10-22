from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_domain_api_v1_tenant_domains_post_response_create_domain_api_v1_tenant_domains_post import (
    CreateDomainApiV1TenantDomainsPostResponseCreateDomainApiV1TenantDomainsPost,
)
from ...models.domain_create import DomainCreate
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    *,
    body: DomainCreate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/tenant/domains",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateDomainApiV1TenantDomainsPostResponseCreateDomainApiV1TenantDomainsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = (
            CreateDomainApiV1TenantDomainsPostResponseCreateDomainApiV1TenantDomainsPost.from_dict(
                response.json()
            )
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
    CreateDomainApiV1TenantDomainsPostResponseCreateDomainApiV1TenantDomainsPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: DomainCreate,
) -> Response[
    CreateDomainApiV1TenantDomainsPostResponseCreateDomainApiV1TenantDomainsPost
    | HTTPValidationError
]:
    """Create Domain

    Args:
        body (DomainCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateDomainApiV1TenantDomainsPostResponseCreateDomainApiV1TenantDomainsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: DomainCreate,
) -> (
    CreateDomainApiV1TenantDomainsPostResponseCreateDomainApiV1TenantDomainsPost
    | HTTPValidationError
    | None
):
    """Create Domain

    Args:
        body (DomainCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateDomainApiV1TenantDomainsPostResponseCreateDomainApiV1TenantDomainsPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: DomainCreate,
) -> Response[
    CreateDomainApiV1TenantDomainsPostResponseCreateDomainApiV1TenantDomainsPost
    | HTTPValidationError
]:
    """Create Domain

    Args:
        body (DomainCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateDomainApiV1TenantDomainsPostResponseCreateDomainApiV1TenantDomainsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: DomainCreate,
) -> (
    CreateDomainApiV1TenantDomainsPostResponseCreateDomainApiV1TenantDomainsPost
    | HTTPValidationError
    | None
):
    """Create Domain

    Args:
        body (DomainCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateDomainApiV1TenantDomainsPostResponseCreateDomainApiV1TenantDomainsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
