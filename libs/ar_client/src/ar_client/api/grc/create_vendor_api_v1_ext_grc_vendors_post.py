from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_vendor_api_v1_ext_grc_vendors_post_body import (
    CreateVendorApiV1ExtGrcVendorsPostBody,
)
from ...models.create_vendor_api_v1_ext_grc_vendors_post_response_create_vendor_api_v1_ext_grc_vendors_post import (
    CreateVendorApiV1ExtGrcVendorsPostResponseCreateVendorApiV1ExtGrcVendorsPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    *,
    body: CreateVendorApiV1ExtGrcVendorsPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/vendors",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateVendorApiV1ExtGrcVendorsPostResponseCreateVendorApiV1ExtGrcVendorsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = (
            CreateVendorApiV1ExtGrcVendorsPostResponseCreateVendorApiV1ExtGrcVendorsPost.from_dict(
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
    CreateVendorApiV1ExtGrcVendorsPostResponseCreateVendorApiV1ExtGrcVendorsPost
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
    body: CreateVendorApiV1ExtGrcVendorsPostBody,
) -> Response[
    CreateVendorApiV1ExtGrcVendorsPostResponseCreateVendorApiV1ExtGrcVendorsPost
    | HTTPValidationError
]:
    """Create Vendor

    Args:
        body (CreateVendorApiV1ExtGrcVendorsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateVendorApiV1ExtGrcVendorsPostResponseCreateVendorApiV1ExtGrcVendorsPost | HTTPValidationError]
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
    body: CreateVendorApiV1ExtGrcVendorsPostBody,
) -> (
    CreateVendorApiV1ExtGrcVendorsPostResponseCreateVendorApiV1ExtGrcVendorsPost
    | HTTPValidationError
    | None
):
    """Create Vendor

    Args:
        body (CreateVendorApiV1ExtGrcVendorsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateVendorApiV1ExtGrcVendorsPostResponseCreateVendorApiV1ExtGrcVendorsPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateVendorApiV1ExtGrcVendorsPostBody,
) -> Response[
    CreateVendorApiV1ExtGrcVendorsPostResponseCreateVendorApiV1ExtGrcVendorsPost
    | HTTPValidationError
]:
    """Create Vendor

    Args:
        body (CreateVendorApiV1ExtGrcVendorsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateVendorApiV1ExtGrcVendorsPostResponseCreateVendorApiV1ExtGrcVendorsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: CreateVendorApiV1ExtGrcVendorsPostBody,
) -> (
    CreateVendorApiV1ExtGrcVendorsPostResponseCreateVendorApiV1ExtGrcVendorsPost
    | HTTPValidationError
    | None
):
    """Create Vendor

    Args:
        body (CreateVendorApiV1ExtGrcVendorsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateVendorApiV1ExtGrcVendorsPostResponseCreateVendorApiV1ExtGrcVendorsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
