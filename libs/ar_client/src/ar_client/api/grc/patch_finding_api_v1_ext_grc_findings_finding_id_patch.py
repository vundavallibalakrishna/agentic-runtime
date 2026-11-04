from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_finding_api_v1_ext_grc_findings_finding_id_patch_body import (
    PatchFindingApiV1ExtGrcFindingsFindingIdPatchBody,
)
from ...models.patch_finding_api_v1_ext_grc_findings_finding_id_patch_response_patch_finding_api_v1_ext_grc_findings_finding_id_patch import (
    PatchFindingApiV1ExtGrcFindingsFindingIdPatchResponsePatchFindingApiV1ExtGrcFindingsFindingIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    finding_id: UUID,
    *,
    body: PatchFindingApiV1ExtGrcFindingsFindingIdPatchBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/ext/grc/findings/{finding_id}".format(
            finding_id=quote(str(finding_id), safe=""),
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
    | PatchFindingApiV1ExtGrcFindingsFindingIdPatchResponsePatchFindingApiV1ExtGrcFindingsFindingIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchFindingApiV1ExtGrcFindingsFindingIdPatchResponsePatchFindingApiV1ExtGrcFindingsFindingIdPatch.from_dict(
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
    | PatchFindingApiV1ExtGrcFindingsFindingIdPatchResponsePatchFindingApiV1ExtGrcFindingsFindingIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    finding_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchFindingApiV1ExtGrcFindingsFindingIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchFindingApiV1ExtGrcFindingsFindingIdPatchResponsePatchFindingApiV1ExtGrcFindingsFindingIdPatch
]:
    """Patch Finding

    Args:
        finding_id (UUID):
        body (PatchFindingApiV1ExtGrcFindingsFindingIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchFindingApiV1ExtGrcFindingsFindingIdPatchResponsePatchFindingApiV1ExtGrcFindingsFindingIdPatch]
    """

    kwargs = _get_kwargs(
        finding_id=finding_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    finding_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchFindingApiV1ExtGrcFindingsFindingIdPatchBody,
) -> (
    HTTPValidationError
    | PatchFindingApiV1ExtGrcFindingsFindingIdPatchResponsePatchFindingApiV1ExtGrcFindingsFindingIdPatch
    | None
):
    """Patch Finding

    Args:
        finding_id (UUID):
        body (PatchFindingApiV1ExtGrcFindingsFindingIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchFindingApiV1ExtGrcFindingsFindingIdPatchResponsePatchFindingApiV1ExtGrcFindingsFindingIdPatch
    """

    return sync_detailed(
        finding_id=finding_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    finding_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchFindingApiV1ExtGrcFindingsFindingIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchFindingApiV1ExtGrcFindingsFindingIdPatchResponsePatchFindingApiV1ExtGrcFindingsFindingIdPatch
]:
    """Patch Finding

    Args:
        finding_id (UUID):
        body (PatchFindingApiV1ExtGrcFindingsFindingIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchFindingApiV1ExtGrcFindingsFindingIdPatchResponsePatchFindingApiV1ExtGrcFindingsFindingIdPatch]
    """

    kwargs = _get_kwargs(
        finding_id=finding_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    finding_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchFindingApiV1ExtGrcFindingsFindingIdPatchBody,
) -> (
    HTTPValidationError
    | PatchFindingApiV1ExtGrcFindingsFindingIdPatchResponsePatchFindingApiV1ExtGrcFindingsFindingIdPatch
    | None
):
    """Patch Finding

    Args:
        finding_id (UUID):
        body (PatchFindingApiV1ExtGrcFindingsFindingIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchFindingApiV1ExtGrcFindingsFindingIdPatchResponsePatchFindingApiV1ExtGrcFindingsFindingIdPatch
    """

    return (
        await asyncio_detailed(
            finding_id=finding_id,
            client=client,
            body=body,
        )
    ).parsed
