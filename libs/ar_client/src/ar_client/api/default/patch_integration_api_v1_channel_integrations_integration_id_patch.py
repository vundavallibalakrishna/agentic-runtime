from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.integration_patch import IntegrationPatch
from ...models.patch_integration_api_v1_channel_integrations_integration_id_patch_response_patch_integration_api_v1_channel_integrations_integration_id_patch import (
    PatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatchResponsePatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    integration_id: UUID,
    *,
    body: IntegrationPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/channel-integrations/{integration_id}".format(
            integration_id=quote(str(integration_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | PatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatchResponsePatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatchResponsePatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatch.from_dict(
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
    | PatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatchResponsePatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatch
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
    body: IntegrationPatch,
) -> Response[
    HTTPValidationError
    | PatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatchResponsePatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatch
]:
    """Patch Integration

    Args:
        integration_id (UUID):
        body (IntegrationPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatchResponsePatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatch]
    """

    kwargs = _get_kwargs(
        integration_id=integration_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    integration_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: IntegrationPatch,
) -> (
    HTTPValidationError
    | PatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatchResponsePatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatch
    | None
):
    """Patch Integration

    Args:
        integration_id (UUID):
        body (IntegrationPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatchResponsePatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatch
    """

    return sync_detailed(
        integration_id=integration_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    integration_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: IntegrationPatch,
) -> Response[
    HTTPValidationError
    | PatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatchResponsePatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatch
]:
    """Patch Integration

    Args:
        integration_id (UUID):
        body (IntegrationPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatchResponsePatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatch]
    """

    kwargs = _get_kwargs(
        integration_id=integration_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    integration_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: IntegrationPatch,
) -> (
    HTTPValidationError
    | PatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatchResponsePatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatch
    | None
):
    """Patch Integration

    Args:
        integration_id (UUID):
        body (IntegrationPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatchResponsePatchIntegrationApiV1ChannelIntegrationsIntegrationIdPatch
    """

    return (
        await asyncio_detailed(
            integration_id=integration_id,
            client=client,
            body=body,
        )
    ).parsed
