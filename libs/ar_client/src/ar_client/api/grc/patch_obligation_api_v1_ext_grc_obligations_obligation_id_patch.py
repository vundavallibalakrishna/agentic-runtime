from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_obligation_api_v1_ext_grc_obligations_obligation_id_patch_body import (
    PatchObligationApiV1ExtGrcObligationsObligationIdPatchBody,
)
from ...models.patch_obligation_api_v1_ext_grc_obligations_obligation_id_patch_response_patch_obligation_api_v1_ext_grc_obligations_obligation_id_patch import (
    PatchObligationApiV1ExtGrcObligationsObligationIdPatchResponsePatchObligationApiV1ExtGrcObligationsObligationIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    obligation_id: UUID,
    *,
    body: PatchObligationApiV1ExtGrcObligationsObligationIdPatchBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/ext/grc/obligations/{obligation_id}".format(
            obligation_id=quote(str(obligation_id), safe=""),
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
    | PatchObligationApiV1ExtGrcObligationsObligationIdPatchResponsePatchObligationApiV1ExtGrcObligationsObligationIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchObligationApiV1ExtGrcObligationsObligationIdPatchResponsePatchObligationApiV1ExtGrcObligationsObligationIdPatch.from_dict(
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
    | PatchObligationApiV1ExtGrcObligationsObligationIdPatchResponsePatchObligationApiV1ExtGrcObligationsObligationIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    obligation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchObligationApiV1ExtGrcObligationsObligationIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchObligationApiV1ExtGrcObligationsObligationIdPatchResponsePatchObligationApiV1ExtGrcObligationsObligationIdPatch
]:
    """Patch Obligation

    Args:
        obligation_id (UUID):
        body (PatchObligationApiV1ExtGrcObligationsObligationIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchObligationApiV1ExtGrcObligationsObligationIdPatchResponsePatchObligationApiV1ExtGrcObligationsObligationIdPatch]
    """

    kwargs = _get_kwargs(
        obligation_id=obligation_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    obligation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchObligationApiV1ExtGrcObligationsObligationIdPatchBody,
) -> (
    HTTPValidationError
    | PatchObligationApiV1ExtGrcObligationsObligationIdPatchResponsePatchObligationApiV1ExtGrcObligationsObligationIdPatch
    | None
):
    """Patch Obligation

    Args:
        obligation_id (UUID):
        body (PatchObligationApiV1ExtGrcObligationsObligationIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchObligationApiV1ExtGrcObligationsObligationIdPatchResponsePatchObligationApiV1ExtGrcObligationsObligationIdPatch
    """

    return sync_detailed(
        obligation_id=obligation_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    obligation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchObligationApiV1ExtGrcObligationsObligationIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchObligationApiV1ExtGrcObligationsObligationIdPatchResponsePatchObligationApiV1ExtGrcObligationsObligationIdPatch
]:
    """Patch Obligation

    Args:
        obligation_id (UUID):
        body (PatchObligationApiV1ExtGrcObligationsObligationIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchObligationApiV1ExtGrcObligationsObligationIdPatchResponsePatchObligationApiV1ExtGrcObligationsObligationIdPatch]
    """

    kwargs = _get_kwargs(
        obligation_id=obligation_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    obligation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchObligationApiV1ExtGrcObligationsObligationIdPatchBody,
) -> (
    HTTPValidationError
    | PatchObligationApiV1ExtGrcObligationsObligationIdPatchResponsePatchObligationApiV1ExtGrcObligationsObligationIdPatch
    | None
):
    """Patch Obligation

    Args:
        obligation_id (UUID):
        body (PatchObligationApiV1ExtGrcObligationsObligationIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchObligationApiV1ExtGrcObligationsObligationIdPatchResponsePatchObligationApiV1ExtGrcObligationsObligationIdPatch
    """

    return (
        await asyncio_detailed(
            obligation_id=obligation_id,
            client=client,
            body=body,
        )
    ).parsed
