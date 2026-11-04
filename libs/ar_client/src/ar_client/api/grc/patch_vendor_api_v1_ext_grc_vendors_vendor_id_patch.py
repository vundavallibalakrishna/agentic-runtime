from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_vendor_api_v1_ext_grc_vendors_vendor_id_patch_body import (
    PatchVendorApiV1ExtGrcVendorsVendorIdPatchBody,
)
from ...models.patch_vendor_api_v1_ext_grc_vendors_vendor_id_patch_response_patch_vendor_api_v1_ext_grc_vendors_vendor_id_patch import (
    PatchVendorApiV1ExtGrcVendorsVendorIdPatchResponsePatchVendorApiV1ExtGrcVendorsVendorIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    vendor_id: UUID,
    *,
    body: PatchVendorApiV1ExtGrcVendorsVendorIdPatchBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/ext/grc/vendors/{vendor_id}".format(
            vendor_id=quote(str(vendor_id), safe=""),
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
    | PatchVendorApiV1ExtGrcVendorsVendorIdPatchResponsePatchVendorApiV1ExtGrcVendorsVendorIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchVendorApiV1ExtGrcVendorsVendorIdPatchResponsePatchVendorApiV1ExtGrcVendorsVendorIdPatch.from_dict(
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
    | PatchVendorApiV1ExtGrcVendorsVendorIdPatchResponsePatchVendorApiV1ExtGrcVendorsVendorIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    vendor_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchVendorApiV1ExtGrcVendorsVendorIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchVendorApiV1ExtGrcVendorsVendorIdPatchResponsePatchVendorApiV1ExtGrcVendorsVendorIdPatch
]:
    """Patch Vendor

    Args:
        vendor_id (UUID):
        body (PatchVendorApiV1ExtGrcVendorsVendorIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchVendorApiV1ExtGrcVendorsVendorIdPatchResponsePatchVendorApiV1ExtGrcVendorsVendorIdPatch]
    """

    kwargs = _get_kwargs(
        vendor_id=vendor_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    vendor_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchVendorApiV1ExtGrcVendorsVendorIdPatchBody,
) -> (
    HTTPValidationError
    | PatchVendorApiV1ExtGrcVendorsVendorIdPatchResponsePatchVendorApiV1ExtGrcVendorsVendorIdPatch
    | None
):
    """Patch Vendor

    Args:
        vendor_id (UUID):
        body (PatchVendorApiV1ExtGrcVendorsVendorIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchVendorApiV1ExtGrcVendorsVendorIdPatchResponsePatchVendorApiV1ExtGrcVendorsVendorIdPatch
    """

    return sync_detailed(
        vendor_id=vendor_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    vendor_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchVendorApiV1ExtGrcVendorsVendorIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchVendorApiV1ExtGrcVendorsVendorIdPatchResponsePatchVendorApiV1ExtGrcVendorsVendorIdPatch
]:
    """Patch Vendor

    Args:
        vendor_id (UUID):
        body (PatchVendorApiV1ExtGrcVendorsVendorIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchVendorApiV1ExtGrcVendorsVendorIdPatchResponsePatchVendorApiV1ExtGrcVendorsVendorIdPatch]
    """

    kwargs = _get_kwargs(
        vendor_id=vendor_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    vendor_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchVendorApiV1ExtGrcVendorsVendorIdPatchBody,
) -> (
    HTTPValidationError
    | PatchVendorApiV1ExtGrcVendorsVendorIdPatchResponsePatchVendorApiV1ExtGrcVendorsVendorIdPatch
    | None
):
    """Patch Vendor

    Args:
        vendor_id (UUID):
        body (PatchVendorApiV1ExtGrcVendorsVendorIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchVendorApiV1ExtGrcVendorsVendorIdPatchResponsePatchVendorApiV1ExtGrcVendorsVendorIdPatch
    """

    return (
        await asyncio_detailed(
            vendor_id=vendor_id,
            client=client,
            body=body,
        )
    ).parsed
