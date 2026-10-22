from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_integration_api_v1_channel_integrations_post_response_create_integration_api_v1_channel_integrations_post import (
    CreateIntegrationApiV1ChannelIntegrationsPostResponseCreateIntegrationApiV1ChannelIntegrationsPost,
)
from ...models.http_validation_error import HTTPValidationError
from ...models.integration_body import IntegrationBody
from typing import cast


def _get_kwargs(
    *,
    body: IntegrationBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/channel-integrations",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateIntegrationApiV1ChannelIntegrationsPostResponseCreateIntegrationApiV1ChannelIntegrationsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 201:
        response_201 = CreateIntegrationApiV1ChannelIntegrationsPostResponseCreateIntegrationApiV1ChannelIntegrationsPost.from_dict(
            response.json()
        )

        return response_201

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
    CreateIntegrationApiV1ChannelIntegrationsPostResponseCreateIntegrationApiV1ChannelIntegrationsPost
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
    body: IntegrationBody,
) -> Response[
    CreateIntegrationApiV1ChannelIntegrationsPostResponseCreateIntegrationApiV1ChannelIntegrationsPost
    | HTTPValidationError
]:
    """Create Integration

    Args:
        body (IntegrationBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateIntegrationApiV1ChannelIntegrationsPostResponseCreateIntegrationApiV1ChannelIntegrationsPost | HTTPValidationError]
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
    body: IntegrationBody,
) -> (
    CreateIntegrationApiV1ChannelIntegrationsPostResponseCreateIntegrationApiV1ChannelIntegrationsPost
    | HTTPValidationError
    | None
):
    """Create Integration

    Args:
        body (IntegrationBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateIntegrationApiV1ChannelIntegrationsPostResponseCreateIntegrationApiV1ChannelIntegrationsPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: IntegrationBody,
) -> Response[
    CreateIntegrationApiV1ChannelIntegrationsPostResponseCreateIntegrationApiV1ChannelIntegrationsPost
    | HTTPValidationError
]:
    """Create Integration

    Args:
        body (IntegrationBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateIntegrationApiV1ChannelIntegrationsPostResponseCreateIntegrationApiV1ChannelIntegrationsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: IntegrationBody,
) -> (
    CreateIntegrationApiV1ChannelIntegrationsPostResponseCreateIntegrationApiV1ChannelIntegrationsPost
    | HTTPValidationError
    | None
):
    """Create Integration

    Args:
        body (IntegrationBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateIntegrationApiV1ChannelIntegrationsPostResponseCreateIntegrationApiV1ChannelIntegrationsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
