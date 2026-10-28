from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.disable_pack_api_v1_tenant_packs_pack_id_disable_post_response_disable_pack_api_v1_tenant_packs_pack_id_disable_post import (
    DisablePackApiV1TenantPacksPackIdDisablePostResponseDisablePackApiV1TenantPacksPackIdDisablePost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    pack_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/tenant/packs/{pack_id}:disable".format(
            pack_id=quote(str(pack_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DisablePackApiV1TenantPacksPackIdDisablePostResponseDisablePackApiV1TenantPacksPackIdDisablePost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DisablePackApiV1TenantPacksPackIdDisablePostResponseDisablePackApiV1TenantPacksPackIdDisablePost.from_dict(
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
    DisablePackApiV1TenantPacksPackIdDisablePostResponseDisablePackApiV1TenantPacksPackIdDisablePost
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
    DisablePackApiV1TenantPacksPackIdDisablePostResponseDisablePackApiV1TenantPacksPackIdDisablePost
    | HTTPValidationError
]:
    """Disable Pack

    Args:
        pack_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DisablePackApiV1TenantPacksPackIdDisablePostResponseDisablePackApiV1TenantPacksPackIdDisablePost | HTTPValidationError]
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
    DisablePackApiV1TenantPacksPackIdDisablePostResponseDisablePackApiV1TenantPacksPackIdDisablePost
    | HTTPValidationError
    | None
):
    """Disable Pack

    Args:
        pack_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DisablePackApiV1TenantPacksPackIdDisablePostResponseDisablePackApiV1TenantPacksPackIdDisablePost | HTTPValidationError
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
    DisablePackApiV1TenantPacksPackIdDisablePostResponseDisablePackApiV1TenantPacksPackIdDisablePost
    | HTTPValidationError
]:
    """Disable Pack

    Args:
        pack_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DisablePackApiV1TenantPacksPackIdDisablePostResponseDisablePackApiV1TenantPacksPackIdDisablePost | HTTPValidationError]
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
    DisablePackApiV1TenantPacksPackIdDisablePostResponseDisablePackApiV1TenantPacksPackIdDisablePost
    | HTTPValidationError
    | None
):
    """Disable Pack

    Args:
        pack_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DisablePackApiV1TenantPacksPackIdDisablePostResponseDisablePackApiV1TenantPacksPackIdDisablePost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            pack_id=pack_id,
            client=client,
        )
    ).parsed
