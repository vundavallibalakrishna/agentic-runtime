from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_role_api_v1_roles_role_id_patch_response_patch_role_api_v1_roles_role_id_patch import PatchRoleApiV1RolesRoleIdPatchResponsePatchRoleApiV1RolesRoleIdPatch
from ...models.role_patch import RolePatch
from typing import cast
from uuid import UUID



def _get_kwargs(
    role_id: UUID,
    *,
    body: RolePatch,

) -> dict[str, Any]:
    headers: dict[str, Any] = {}


    

    

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/roles/{role_id}".format(role_id=quote(str(role_id), safe=""),),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | PatchRoleApiV1RolesRoleIdPatchResponsePatchRoleApiV1RolesRoleIdPatch | None:
    if response.status_code == 200:
        response_200 = PatchRoleApiV1RolesRoleIdPatchResponsePatchRoleApiV1RolesRoleIdPatch.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | PatchRoleApiV1RolesRoleIdPatchResponsePatchRoleApiV1RolesRoleIdPatch]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    role_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: RolePatch,

) -> Response[HTTPValidationError | PatchRoleApiV1RolesRoleIdPatchResponsePatchRoleApiV1RolesRoleIdPatch]:
    """ Patch Role

    Args:
        role_id (UUID):
        body (RolePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchRoleApiV1RolesRoleIdPatchResponsePatchRoleApiV1RolesRoleIdPatch]
     """


    kwargs = _get_kwargs(
        role_id=role_id,
body=body,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    role_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: RolePatch,

) -> HTTPValidationError | PatchRoleApiV1RolesRoleIdPatchResponsePatchRoleApiV1RolesRoleIdPatch | None:
    """ Patch Role

    Args:
        role_id (UUID):
        body (RolePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchRoleApiV1RolesRoleIdPatchResponsePatchRoleApiV1RolesRoleIdPatch
     """


    return sync_detailed(
        role_id=role_id,
client=client,
body=body,

    ).parsed

async def asyncio_detailed(
    role_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: RolePatch,

) -> Response[HTTPValidationError | PatchRoleApiV1RolesRoleIdPatchResponsePatchRoleApiV1RolesRoleIdPatch]:
    """ Patch Role

    Args:
        role_id (UUID):
        body (RolePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchRoleApiV1RolesRoleIdPatchResponsePatchRoleApiV1RolesRoleIdPatch]
     """


    kwargs = _get_kwargs(
        role_id=role_id,
body=body,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    role_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: RolePatch,

) -> HTTPValidationError | PatchRoleApiV1RolesRoleIdPatchResponsePatchRoleApiV1RolesRoleIdPatch | None:
    """ Patch Role

    Args:
        role_id (UUID):
        body (RolePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchRoleApiV1RolesRoleIdPatchResponsePatchRoleApiV1RolesRoleIdPatch
     """


    return (await asyncio_detailed(
        role_id=role_id,
client=client,
body=body,

    )).parsed
