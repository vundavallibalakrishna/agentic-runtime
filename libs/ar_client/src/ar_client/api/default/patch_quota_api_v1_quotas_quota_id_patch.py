from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_quota_api_v1_quotas_quota_id_patch_response_patch_quota_api_v1_quotas_quota_id_patch import (
    PatchQuotaApiV1QuotasQuotaIdPatchResponsePatchQuotaApiV1QuotasQuotaIdPatch,
)
from ...models.quota_patch import QuotaPatch
from typing import cast
from uuid import UUID


def _get_kwargs(
    quota_id: UUID,
    *,
    body: QuotaPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/quotas/{quota_id}".format(
            quota_id=quote(str(quota_id), safe=""),
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
    | PatchQuotaApiV1QuotasQuotaIdPatchResponsePatchQuotaApiV1QuotasQuotaIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = (
            PatchQuotaApiV1QuotasQuotaIdPatchResponsePatchQuotaApiV1QuotasQuotaIdPatch.from_dict(
                response.json()
            )
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
    HTTPValidationError | PatchQuotaApiV1QuotasQuotaIdPatchResponsePatchQuotaApiV1QuotasQuotaIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    quota_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: QuotaPatch,
) -> Response[
    HTTPValidationError | PatchQuotaApiV1QuotasQuotaIdPatchResponsePatchQuotaApiV1QuotasQuotaIdPatch
]:
    """Patch Quota

    Args:
        quota_id (UUID):
        body (QuotaPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchQuotaApiV1QuotasQuotaIdPatchResponsePatchQuotaApiV1QuotasQuotaIdPatch]
    """

    kwargs = _get_kwargs(
        quota_id=quota_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    quota_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: QuotaPatch,
) -> (
    HTTPValidationError
    | PatchQuotaApiV1QuotasQuotaIdPatchResponsePatchQuotaApiV1QuotasQuotaIdPatch
    | None
):
    """Patch Quota

    Args:
        quota_id (UUID):
        body (QuotaPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchQuotaApiV1QuotasQuotaIdPatchResponsePatchQuotaApiV1QuotasQuotaIdPatch
    """

    return sync_detailed(
        quota_id=quota_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    quota_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: QuotaPatch,
) -> Response[
    HTTPValidationError | PatchQuotaApiV1QuotasQuotaIdPatchResponsePatchQuotaApiV1QuotasQuotaIdPatch
]:
    """Patch Quota

    Args:
        quota_id (UUID):
        body (QuotaPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchQuotaApiV1QuotasQuotaIdPatchResponsePatchQuotaApiV1QuotasQuotaIdPatch]
    """

    kwargs = _get_kwargs(
        quota_id=quota_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    quota_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: QuotaPatch,
) -> (
    HTTPValidationError
    | PatchQuotaApiV1QuotasQuotaIdPatchResponsePatchQuotaApiV1QuotasQuotaIdPatch
    | None
):
    """Patch Quota

    Args:
        quota_id (UUID):
        body (QuotaPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchQuotaApiV1QuotasQuotaIdPatchResponsePatchQuotaApiV1QuotasQuotaIdPatch
    """

    return (
        await asyncio_detailed(
            quota_id=quota_id,
            client=client,
            body=body,
        )
    ).parsed
