from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.test_integration_api_v1_channel_integrations_integration_id_test_post_response_test_integration_api_v1_channel_integrations_integration_id_test_post import (
    TestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPostResponseTestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    integration_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/channel-integrations/{integration_id}:test".format(
            integration_id=quote(str(integration_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | TestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPostResponseTestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPost
    | None
):
    if response.status_code == 200:
        response_200 = TestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPostResponseTestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPost.from_dict(
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
    | TestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPostResponseTestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    integration_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | TestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPostResponseTestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPost
]:
    """Test Integration

    Args:
        integration_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | TestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPostResponseTestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPost]
    """

    kwargs = _get_kwargs(
        integration_id=integration_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    integration_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | TestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPostResponseTestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPost
    | None
):
    """Test Integration

    Args:
        integration_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | TestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPostResponseTestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPost
    """

    return sync_detailed(
        integration_id=integration_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    integration_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | TestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPostResponseTestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPost
]:
    """Test Integration

    Args:
        integration_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | TestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPostResponseTestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPost]
    """

    kwargs = _get_kwargs(
        integration_id=integration_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    integration_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | TestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPostResponseTestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPost
    | None
):
    """Test Integration

    Args:
        integration_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | TestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPostResponseTestIntegrationApiV1ChannelIntegrationsIntegrationIdTestPost
    """

    return (
        await asyncio_detailed(
            integration_id=integration_id,
            client=client,
        )
    ).parsed
