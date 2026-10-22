from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_service_account_api_v1_service_accounts_service_account_id_patch_response_patch_service_account_api_v1_service_accounts_service_account_id_patch import (
    PatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatchResponsePatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatch,
)
from ...models.service_account_patch import ServiceAccountPatch
from typing import cast
from uuid import UUID


def _get_kwargs(
    service_account_id: UUID,
    *,
    body: ServiceAccountPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/service-accounts/{service_account_id}".format(
            service_account_id=quote(str(service_account_id), safe=""),
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
    | PatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatchResponsePatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatchResponsePatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatch.from_dict(
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
    | PatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatchResponsePatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    service_account_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ServiceAccountPatch,
) -> Response[
    HTTPValidationError
    | PatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatchResponsePatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatch
]:
    """Patch Service Account

    Args:
        service_account_id (UUID):
        body (ServiceAccountPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatchResponsePatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatch]
    """

    kwargs = _get_kwargs(
        service_account_id=service_account_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    service_account_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ServiceAccountPatch,
) -> (
    HTTPValidationError
    | PatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatchResponsePatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatch
    | None
):
    """Patch Service Account

    Args:
        service_account_id (UUID):
        body (ServiceAccountPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatchResponsePatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatch
    """

    return sync_detailed(
        service_account_id=service_account_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    service_account_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ServiceAccountPatch,
) -> Response[
    HTTPValidationError
    | PatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatchResponsePatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatch
]:
    """Patch Service Account

    Args:
        service_account_id (UUID):
        body (ServiceAccountPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatchResponsePatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatch]
    """

    kwargs = _get_kwargs(
        service_account_id=service_account_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    service_account_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ServiceAccountPatch,
) -> (
    HTTPValidationError
    | PatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatchResponsePatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatch
    | None
):
    """Patch Service Account

    Args:
        service_account_id (UUID):
        body (ServiceAccountPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatchResponsePatchServiceAccountApiV1ServiceAccountsServiceAccountIdPatch
    """

    return (
        await asyncio_detailed(
            service_account_id=service_account_id,
            client=client,
            body=body,
        )
    ).parsed
