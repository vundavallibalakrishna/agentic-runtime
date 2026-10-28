from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_pbc_api_v1_ext_grc_pbc_requests_request_id_patch_body import (
    PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchBody,
)
from ...models.patch_pbc_api_v1_ext_grc_pbc_requests_request_id_patch_response_patch_pbc_api_v1_ext_grc_pbc_requests_request_id_patch import (
    PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchResponsePatchPbcApiV1ExtGrcPbcRequestsRequestIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    request_id: UUID,
    *,
    body: PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/ext/grc/pbc-requests/{request_id}".format(
            request_id=quote(str(request_id), safe=""),
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
    | PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchResponsePatchPbcApiV1ExtGrcPbcRequestsRequestIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchResponsePatchPbcApiV1ExtGrcPbcRequestsRequestIdPatch.from_dict(
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
    | PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchResponsePatchPbcApiV1ExtGrcPbcRequestsRequestIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    request_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchResponsePatchPbcApiV1ExtGrcPbcRequestsRequestIdPatch
]:
    """Patch Pbc

    Args:
        request_id (UUID):
        body (PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchResponsePatchPbcApiV1ExtGrcPbcRequestsRequestIdPatch]
    """

    kwargs = _get_kwargs(
        request_id=request_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    request_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchBody,
) -> (
    HTTPValidationError
    | PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchResponsePatchPbcApiV1ExtGrcPbcRequestsRequestIdPatch
    | None
):
    """Patch Pbc

    Args:
        request_id (UUID):
        body (PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchResponsePatchPbcApiV1ExtGrcPbcRequestsRequestIdPatch
    """

    return sync_detailed(
        request_id=request_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    request_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchResponsePatchPbcApiV1ExtGrcPbcRequestsRequestIdPatch
]:
    """Patch Pbc

    Args:
        request_id (UUID):
        body (PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchResponsePatchPbcApiV1ExtGrcPbcRequestsRequestIdPatch]
    """

    kwargs = _get_kwargs(
        request_id=request_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    request_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchBody,
) -> (
    HTTPValidationError
    | PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchResponsePatchPbcApiV1ExtGrcPbcRequestsRequestIdPatch
    | None
):
    """Patch Pbc

    Args:
        request_id (UUID):
        body (PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchPbcApiV1ExtGrcPbcRequestsRequestIdPatchResponsePatchPbcApiV1ExtGrcPbcRequestsRequestIdPatch
    """

    return (
        await asyncio_detailed(
            request_id=request_id,
            client=client,
            body=body,
        )
    ).parsed
