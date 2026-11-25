from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_capabilities_api_v1_service_accounts_capabilities_get_response_list_capabilities_api_v1_service_accounts_capabilities_get import (
    ListCapabilitiesApiV1ServiceAccountsCapabilitiesGetResponseListCapabilitiesApiV1ServiceAccountsCapabilitiesGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/service-accounts:capabilities",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ListCapabilitiesApiV1ServiceAccountsCapabilitiesGetResponseListCapabilitiesApiV1ServiceAccountsCapabilitiesGet
    | None
):
    if response.status_code == 200:
        response_200 = ListCapabilitiesApiV1ServiceAccountsCapabilitiesGetResponseListCapabilitiesApiV1ServiceAccountsCapabilitiesGet.from_dict(
            response.json()
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    ListCapabilitiesApiV1ServiceAccountsCapabilitiesGetResponseListCapabilitiesApiV1ServiceAccountsCapabilitiesGet
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
) -> Response[
    ListCapabilitiesApiV1ServiceAccountsCapabilitiesGetResponseListCapabilitiesApiV1ServiceAccountsCapabilitiesGet
]:
    """List Capabilities

     What a service account can be made for: the role and the permissions for each.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListCapabilitiesApiV1ServiceAccountsCapabilitiesGetResponseListCapabilitiesApiV1ServiceAccountsCapabilitiesGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> (
    ListCapabilitiesApiV1ServiceAccountsCapabilitiesGetResponseListCapabilitiesApiV1ServiceAccountsCapabilitiesGet
    | None
):
    """List Capabilities

     What a service account can be made for: the role and the permissions for each.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListCapabilitiesApiV1ServiceAccountsCapabilitiesGetResponseListCapabilitiesApiV1ServiceAccountsCapabilitiesGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ListCapabilitiesApiV1ServiceAccountsCapabilitiesGetResponseListCapabilitiesApiV1ServiceAccountsCapabilitiesGet
]:
    """List Capabilities

     What a service account can be made for: the role and the permissions for each.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListCapabilitiesApiV1ServiceAccountsCapabilitiesGetResponseListCapabilitiesApiV1ServiceAccountsCapabilitiesGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> (
    ListCapabilitiesApiV1ServiceAccountsCapabilitiesGetResponseListCapabilitiesApiV1ServiceAccountsCapabilitiesGet
    | None
):
    """List Capabilities

     What a service account can be made for: the role and the permissions for each.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListCapabilitiesApiV1ServiceAccountsCapabilitiesGetResponseListCapabilitiesApiV1ServiceAccountsCapabilitiesGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
