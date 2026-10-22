from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_domains_api_v1_tenant_domains_get_response_list_domains_api_v1_tenant_domains_get import (
    ListDomainsApiV1TenantDomainsGetResponseListDomainsApiV1TenantDomainsGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/tenant/domains",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ListDomainsApiV1TenantDomainsGetResponseListDomainsApiV1TenantDomainsGet | None:
    if response.status_code == 200:
        response_200 = (
            ListDomainsApiV1TenantDomainsGetResponseListDomainsApiV1TenantDomainsGet.from_dict(
                response.json()
            )
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ListDomainsApiV1TenantDomainsGetResponseListDomainsApiV1TenantDomainsGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListDomainsApiV1TenantDomainsGetResponseListDomainsApiV1TenantDomainsGet]:
    """List Domains

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListDomainsApiV1TenantDomainsGetResponseListDomainsApiV1TenantDomainsGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> ListDomainsApiV1TenantDomainsGetResponseListDomainsApiV1TenantDomainsGet | None:
    """List Domains

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListDomainsApiV1TenantDomainsGetResponseListDomainsApiV1TenantDomainsGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListDomainsApiV1TenantDomainsGetResponseListDomainsApiV1TenantDomainsGet]:
    """List Domains

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListDomainsApiV1TenantDomainsGetResponseListDomainsApiV1TenantDomainsGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> ListDomainsApiV1TenantDomainsGetResponseListDomainsApiV1TenantDomainsGet | None:
    """List Domains

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListDomainsApiV1TenantDomainsGetResponseListDomainsApiV1TenantDomainsGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
