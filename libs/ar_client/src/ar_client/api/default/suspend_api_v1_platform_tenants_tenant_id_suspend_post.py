from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.suspend_api_v1_platform_tenants_tenant_id_suspend_post_response_suspend_api_v1_platform_tenants_tenant_id_suspend_post import (
    SuspendApiV1PlatformTenantsTenantIdSuspendPostResponseSuspendApiV1PlatformTenantsTenantIdSuspendPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    tenant_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/platform/tenants/{tenant_id}:suspend".format(
            tenant_id=quote(str(tenant_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | SuspendApiV1PlatformTenantsTenantIdSuspendPostResponseSuspendApiV1PlatformTenantsTenantIdSuspendPost
    | None
):
    if response.status_code == 200:
        response_200 = SuspendApiV1PlatformTenantsTenantIdSuspendPostResponseSuspendApiV1PlatformTenantsTenantIdSuspendPost.from_dict(
            response.json()
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
    HTTPValidationError
    | SuspendApiV1PlatformTenantsTenantIdSuspendPostResponseSuspendApiV1PlatformTenantsTenantIdSuspendPost
]:
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
) -> Response[
    HTTPValidationError
    | SuspendApiV1PlatformTenantsTenantIdSuspendPostResponseSuspendApiV1PlatformTenantsTenantIdSuspendPost
]:
    """Suspend

    Args:
        tenant_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SuspendApiV1PlatformTenantsTenantIdSuspendPostResponseSuspendApiV1PlatformTenantsTenantIdSuspendPost]
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
) -> (
    HTTPValidationError
    | SuspendApiV1PlatformTenantsTenantIdSuspendPostResponseSuspendApiV1PlatformTenantsTenantIdSuspendPost
    | None
):
    """Suspend

    Args:
        tenant_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SuspendApiV1PlatformTenantsTenantIdSuspendPostResponseSuspendApiV1PlatformTenantsTenantIdSuspendPost
    """

    return sync_detailed(
        tenant_id=tenant_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    tenant_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | SuspendApiV1PlatformTenantsTenantIdSuspendPostResponseSuspendApiV1PlatformTenantsTenantIdSuspendPost
]:
    """Suspend

    Args:
        tenant_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SuspendApiV1PlatformTenantsTenantIdSuspendPostResponseSuspendApiV1PlatformTenantsTenantIdSuspendPost]
    """

    kwargs = _get_kwargs(
        tenant_id=tenant_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    tenant_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | SuspendApiV1PlatformTenantsTenantIdSuspendPostResponseSuspendApiV1PlatformTenantsTenantIdSuspendPost
    | None
):
    """Suspend

    Args:
        tenant_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SuspendApiV1PlatformTenantsTenantIdSuspendPostResponseSuspendApiV1PlatformTenantsTenantIdSuspendPost
    """

    return (
        await asyncio_detailed(
            tenant_id=tenant_id,
            client=client,
        )
    ).parsed
