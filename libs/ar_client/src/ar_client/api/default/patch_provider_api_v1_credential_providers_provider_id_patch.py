from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.credential_provider_patch import CredentialProviderPatch
from ...models.http_validation_error import HTTPValidationError
from ...models.patch_provider_api_v1_credential_providers_provider_id_patch_response_patch_provider_api_v1_credential_providers_provider_id_patch import (
    PatchProviderApiV1CredentialProvidersProviderIdPatchResponsePatchProviderApiV1CredentialProvidersProviderIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    provider_id: UUID,
    *,
    body: CredentialProviderPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/credential-providers/{provider_id}".format(
            provider_id=quote(str(provider_id), safe=""),
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
    | PatchProviderApiV1CredentialProvidersProviderIdPatchResponsePatchProviderApiV1CredentialProvidersProviderIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchProviderApiV1CredentialProvidersProviderIdPatchResponsePatchProviderApiV1CredentialProvidersProviderIdPatch.from_dict(
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
    | PatchProviderApiV1CredentialProvidersProviderIdPatchResponsePatchProviderApiV1CredentialProvidersProviderIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    provider_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CredentialProviderPatch,
) -> Response[
    HTTPValidationError
    | PatchProviderApiV1CredentialProvidersProviderIdPatchResponsePatchProviderApiV1CredentialProvidersProviderIdPatch
]:
    """Patch Provider

    Args:
        provider_id (UUID):
        body (CredentialProviderPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchProviderApiV1CredentialProvidersProviderIdPatchResponsePatchProviderApiV1CredentialProvidersProviderIdPatch]
    """

    kwargs = _get_kwargs(
        provider_id=provider_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    provider_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CredentialProviderPatch,
) -> (
    HTTPValidationError
    | PatchProviderApiV1CredentialProvidersProviderIdPatchResponsePatchProviderApiV1CredentialProvidersProviderIdPatch
    | None
):
    """Patch Provider

    Args:
        provider_id (UUID):
        body (CredentialProviderPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchProviderApiV1CredentialProvidersProviderIdPatchResponsePatchProviderApiV1CredentialProvidersProviderIdPatch
    """

    return sync_detailed(
        provider_id=provider_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    provider_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CredentialProviderPatch,
) -> Response[
    HTTPValidationError
    | PatchProviderApiV1CredentialProvidersProviderIdPatchResponsePatchProviderApiV1CredentialProvidersProviderIdPatch
]:
    """Patch Provider

    Args:
        provider_id (UUID):
        body (CredentialProviderPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchProviderApiV1CredentialProvidersProviderIdPatchResponsePatchProviderApiV1CredentialProvidersProviderIdPatch]
    """

    kwargs = _get_kwargs(
        provider_id=provider_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    provider_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CredentialProviderPatch,
) -> (
    HTTPValidationError
    | PatchProviderApiV1CredentialProvidersProviderIdPatchResponsePatchProviderApiV1CredentialProvidersProviderIdPatch
    | None
):
    """Patch Provider

    Args:
        provider_id (UUID):
        body (CredentialProviderPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchProviderApiV1CredentialProvidersProviderIdPatchResponsePatchProviderApiV1CredentialProvidersProviderIdPatch
    """

    return (
        await asyncio_detailed(
            provider_id=provider_id,
            client=client,
            body=body,
        )
    ).parsed
