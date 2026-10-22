from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.internal_integrations_internal_v1_channels_integrations_get_response_internal_integrations_internal_v1_channels_integrations_get import (
    InternalIntegrationsInternalV1ChannelsIntegrationsGetResponseInternalIntegrationsInternalV1ChannelsIntegrationsGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/internal/v1/channels/integrations",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    InternalIntegrationsInternalV1ChannelsIntegrationsGetResponseInternalIntegrationsInternalV1ChannelsIntegrationsGet
    | None
):
    if response.status_code == 200:
        response_200 = InternalIntegrationsInternalV1ChannelsIntegrationsGetResponseInternalIntegrationsInternalV1ChannelsIntegrationsGet.from_dict(
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
    InternalIntegrationsInternalV1ChannelsIntegrationsGetResponseInternalIntegrationsInternalV1ChannelsIntegrationsGet
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
    InternalIntegrationsInternalV1ChannelsIntegrationsGetResponseInternalIntegrationsInternalV1ChannelsIntegrationsGet
]:
    """Internal Integrations

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[InternalIntegrationsInternalV1ChannelsIntegrationsGetResponseInternalIntegrationsInternalV1ChannelsIntegrationsGet]
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
    InternalIntegrationsInternalV1ChannelsIntegrationsGetResponseInternalIntegrationsInternalV1ChannelsIntegrationsGet
    | None
):
    """Internal Integrations

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        InternalIntegrationsInternalV1ChannelsIntegrationsGetResponseInternalIntegrationsInternalV1ChannelsIntegrationsGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    InternalIntegrationsInternalV1ChannelsIntegrationsGetResponseInternalIntegrationsInternalV1ChannelsIntegrationsGet
]:
    """Internal Integrations

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[InternalIntegrationsInternalV1ChannelsIntegrationsGetResponseInternalIntegrationsInternalV1ChannelsIntegrationsGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> (
    InternalIntegrationsInternalV1ChannelsIntegrationsGetResponseInternalIntegrationsInternalV1ChannelsIntegrationsGet
    | None
):
    """Internal Integrations

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        InternalIntegrationsInternalV1ChannelsIntegrationsGetResponseInternalIntegrationsInternalV1ChannelsIntegrationsGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
