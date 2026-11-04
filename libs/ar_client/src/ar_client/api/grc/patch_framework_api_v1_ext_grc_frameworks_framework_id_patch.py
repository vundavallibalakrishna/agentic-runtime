from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_framework_api_v1_ext_grc_frameworks_framework_id_patch_body import (
    PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchBody,
)
from ...models.patch_framework_api_v1_ext_grc_frameworks_framework_id_patch_response_patch_framework_api_v1_ext_grc_frameworks_framework_id_patch import (
    PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchResponsePatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    framework_id: UUID,
    *,
    body: PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/ext/grc/frameworks/{framework_id}".format(
            framework_id=quote(str(framework_id), safe=""),
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
    | PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchResponsePatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchResponsePatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatch.from_dict(
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
    | PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchResponsePatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    framework_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchResponsePatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatch
]:
    """Patch Framework

    Args:
        framework_id (UUID):
        body (PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchResponsePatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatch]
    """

    kwargs = _get_kwargs(
        framework_id=framework_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    framework_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchBody,
) -> (
    HTTPValidationError
    | PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchResponsePatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatch
    | None
):
    """Patch Framework

    Args:
        framework_id (UUID):
        body (PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchResponsePatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatch
    """

    return sync_detailed(
        framework_id=framework_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    framework_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchResponsePatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatch
]:
    """Patch Framework

    Args:
        framework_id (UUID):
        body (PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchResponsePatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatch]
    """

    kwargs = _get_kwargs(
        framework_id=framework_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    framework_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchBody,
) -> (
    HTTPValidationError
    | PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchResponsePatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatch
    | None
):
    """Patch Framework

    Args:
        framework_id (UUID):
        body (PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatchResponsePatchFrameworkApiV1ExtGrcFrameworksFrameworkIdPatch
    """

    return (
        await asyncio_detailed(
            framework_id=framework_id,
            client=client,
            body=body,
        )
    ).parsed
