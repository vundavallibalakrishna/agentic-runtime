from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_tenant_api_v1_platform_tenants_tenant_id_delete_post_body import (
    DeleteTenantApiV1PlatformTenantsTenantIdDeletePostBody,
)
from ...models.delete_tenant_api_v1_platform_tenants_tenant_id_delete_post_response_delete_tenant_api_v1_platform_tenants_tenant_id_delete_post import (
    DeleteTenantApiV1PlatformTenantsTenantIdDeletePostResponseDeleteTenantApiV1PlatformTenantsTenantIdDeletePost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    tenant_id: UUID,
    *,
    body: DeleteTenantApiV1PlatformTenantsTenantIdDeletePostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/platform/tenants/{tenant_id}:delete".format(
            tenant_id=quote(str(tenant_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeleteTenantApiV1PlatformTenantsTenantIdDeletePostResponseDeleteTenantApiV1PlatformTenantsTenantIdDeletePost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DeleteTenantApiV1PlatformTenantsTenantIdDeletePostResponseDeleteTenantApiV1PlatformTenantsTenantIdDeletePost.from_dict(
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
    DeleteTenantApiV1PlatformTenantsTenantIdDeletePostResponseDeleteTenantApiV1PlatformTenantsTenantIdDeletePost
    | HTTPValidationError
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
    body: DeleteTenantApiV1PlatformTenantsTenantIdDeletePostBody,
) -> Response[
    DeleteTenantApiV1PlatformTenantsTenantIdDeletePostResponseDeleteTenantApiV1PlatformTenantsTenantIdDeletePost
    | HTTPValidationError
]:
    """Delete Tenant

    Args:
        tenant_id (UUID):
        body (DeleteTenantApiV1PlatformTenantsTenantIdDeletePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteTenantApiV1PlatformTenantsTenantIdDeletePostResponseDeleteTenantApiV1PlatformTenantsTenantIdDeletePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        tenant_id=tenant_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    tenant_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DeleteTenantApiV1PlatformTenantsTenantIdDeletePostBody,
) -> (
    DeleteTenantApiV1PlatformTenantsTenantIdDeletePostResponseDeleteTenantApiV1PlatformTenantsTenantIdDeletePost
    | HTTPValidationError
    | None
):
    """Delete Tenant

    Args:
        tenant_id (UUID):
        body (DeleteTenantApiV1PlatformTenantsTenantIdDeletePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteTenantApiV1PlatformTenantsTenantIdDeletePostResponseDeleteTenantApiV1PlatformTenantsTenantIdDeletePost | HTTPValidationError
    """

    return sync_detailed(
        tenant_id=tenant_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    tenant_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DeleteTenantApiV1PlatformTenantsTenantIdDeletePostBody,
) -> Response[
    DeleteTenantApiV1PlatformTenantsTenantIdDeletePostResponseDeleteTenantApiV1PlatformTenantsTenantIdDeletePost
    | HTTPValidationError
]:
    """Delete Tenant

    Args:
        tenant_id (UUID):
        body (DeleteTenantApiV1PlatformTenantsTenantIdDeletePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteTenantApiV1PlatformTenantsTenantIdDeletePostResponseDeleteTenantApiV1PlatformTenantsTenantIdDeletePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        tenant_id=tenant_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    tenant_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DeleteTenantApiV1PlatformTenantsTenantIdDeletePostBody,
) -> (
    DeleteTenantApiV1PlatformTenantsTenantIdDeletePostResponseDeleteTenantApiV1PlatformTenantsTenantIdDeletePost
    | HTTPValidationError
    | None
):
    """Delete Tenant

    Args:
        tenant_id (UUID):
        body (DeleteTenantApiV1PlatformTenantsTenantIdDeletePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteTenantApiV1PlatformTenantsTenantIdDeletePostResponseDeleteTenantApiV1PlatformTenantsTenantIdDeletePost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            tenant_id=tenant_id,
            client=client,
            body=body,
        )
    ).parsed
