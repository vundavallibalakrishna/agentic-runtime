from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.enable_pack_api_v1_tenant_packs_pack_id_enable_post_response_enable_pack_api_v1_tenant_packs_pack_id_enable_post import (
    EnablePackApiV1TenantPacksPackIdEnablePostResponseEnablePackApiV1TenantPacksPackIdEnablePost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    pack_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/tenant/packs/{pack_id}:enable".format(
            pack_id=quote(str(pack_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    EnablePackApiV1TenantPacksPackIdEnablePostResponseEnablePackApiV1TenantPacksPackIdEnablePost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = EnablePackApiV1TenantPacksPackIdEnablePostResponseEnablePackApiV1TenantPacksPackIdEnablePost.from_dict(
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
    EnablePackApiV1TenantPacksPackIdEnablePostResponseEnablePackApiV1TenantPacksPackIdEnablePost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    pack_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    EnablePackApiV1TenantPacksPackIdEnablePostResponseEnablePackApiV1TenantPacksPackIdEnablePost
    | HTTPValidationError
]:
    """Enable Pack

    Args:
        pack_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[EnablePackApiV1TenantPacksPackIdEnablePostResponseEnablePackApiV1TenantPacksPackIdEnablePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        pack_id=pack_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    pack_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> (
    EnablePackApiV1TenantPacksPackIdEnablePostResponseEnablePackApiV1TenantPacksPackIdEnablePost
    | HTTPValidationError
    | None
):
    """Enable Pack

    Args:
        pack_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        EnablePackApiV1TenantPacksPackIdEnablePostResponseEnablePackApiV1TenantPacksPackIdEnablePost | HTTPValidationError
    """

    return sync_detailed(
        pack_id=pack_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    pack_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    EnablePackApiV1TenantPacksPackIdEnablePostResponseEnablePackApiV1TenantPacksPackIdEnablePost
    | HTTPValidationError
]:
    """Enable Pack

    Args:
        pack_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[EnablePackApiV1TenantPacksPackIdEnablePostResponseEnablePackApiV1TenantPacksPackIdEnablePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        pack_id=pack_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    pack_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> (
    EnablePackApiV1TenantPacksPackIdEnablePostResponseEnablePackApiV1TenantPacksPackIdEnablePost
    | HTTPValidationError
    | None
):
    """Enable Pack

    Args:
        pack_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        EnablePackApiV1TenantPacksPackIdEnablePostResponseEnablePackApiV1TenantPacksPackIdEnablePost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            pack_id=pack_id,
            client=client,
        )
    ).parsed
