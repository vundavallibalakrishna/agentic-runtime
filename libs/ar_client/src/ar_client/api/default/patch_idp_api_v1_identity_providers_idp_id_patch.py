from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.idp_create import IdpCreate
from ...models.patch_idp_api_v1_identity_providers_idp_id_patch_response_patch_idp_api_v1_identity_providers_idp_id_patch import (
    PatchIdpApiV1IdentityProvidersIdpIdPatchResponsePatchIdpApiV1IdentityProvidersIdpIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    idp_id: UUID,
    *,
    body: IdpCreate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/identity-providers/{idp_id}".format(
            idp_id=quote(str(idp_id), safe=""),
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
    | PatchIdpApiV1IdentityProvidersIdpIdPatchResponsePatchIdpApiV1IdentityProvidersIdpIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchIdpApiV1IdentityProvidersIdpIdPatchResponsePatchIdpApiV1IdentityProvidersIdpIdPatch.from_dict(
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
    | PatchIdpApiV1IdentityProvidersIdpIdPatchResponsePatchIdpApiV1IdentityProvidersIdpIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    idp_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: IdpCreate,
) -> Response[
    HTTPValidationError
    | PatchIdpApiV1IdentityProvidersIdpIdPatchResponsePatchIdpApiV1IdentityProvidersIdpIdPatch
]:
    """Patch Idp

    Args:
        idp_id (UUID):
        body (IdpCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchIdpApiV1IdentityProvidersIdpIdPatchResponsePatchIdpApiV1IdentityProvidersIdpIdPatch]
    """

    kwargs = _get_kwargs(
        idp_id=idp_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    idp_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: IdpCreate,
) -> (
    HTTPValidationError
    | PatchIdpApiV1IdentityProvidersIdpIdPatchResponsePatchIdpApiV1IdentityProvidersIdpIdPatch
    | None
):
    """Patch Idp

    Args:
        idp_id (UUID):
        body (IdpCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchIdpApiV1IdentityProvidersIdpIdPatchResponsePatchIdpApiV1IdentityProvidersIdpIdPatch
    """

    return sync_detailed(
        idp_id=idp_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    idp_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: IdpCreate,
) -> Response[
    HTTPValidationError
    | PatchIdpApiV1IdentityProvidersIdpIdPatchResponsePatchIdpApiV1IdentityProvidersIdpIdPatch
]:
    """Patch Idp

    Args:
        idp_id (UUID):
        body (IdpCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchIdpApiV1IdentityProvidersIdpIdPatchResponsePatchIdpApiV1IdentityProvidersIdpIdPatch]
    """

    kwargs = _get_kwargs(
        idp_id=idp_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    idp_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: IdpCreate,
) -> (
    HTTPValidationError
    | PatchIdpApiV1IdentityProvidersIdpIdPatchResponsePatchIdpApiV1IdentityProvidersIdpIdPatch
    | None
):
    """Patch Idp

    Args:
        idp_id (UUID):
        body (IdpCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchIdpApiV1IdentityProvidersIdpIdPatchResponsePatchIdpApiV1IdentityProvidersIdpIdPatch
    """

    return (
        await asyncio_detailed(
            idp_id=idp_id,
            client=client,
            body=body,
        )
    ).parsed
