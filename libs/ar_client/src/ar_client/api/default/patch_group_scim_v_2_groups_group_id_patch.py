from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_group_scim_v2_groups_group_id_patch_body import PatchGroupScimV2GroupsGroupIdPatchBody
from ...models.patch_group_scim_v2_groups_group_id_patch_response_patch_group_scim_v2_groups_group_id_patch import PatchGroupScimV2GroupsGroupIdPatchResponsePatchGroupScimV2GroupsGroupIdPatch
from typing import cast
from uuid import UUID



def _get_kwargs(
    group_id: UUID,
    *,
    body: PatchGroupScimV2GroupsGroupIdPatchBody,

) -> dict[str, Any]:
    headers: dict[str, Any] = {}


    

    

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/scim/v2/Groups/{group_id}".format(group_id=quote(str(group_id), safe=""),),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | PatchGroupScimV2GroupsGroupIdPatchResponsePatchGroupScimV2GroupsGroupIdPatch | None:
    if response.status_code == 200:
        response_200 = PatchGroupScimV2GroupsGroupIdPatchResponsePatchGroupScimV2GroupsGroupIdPatch.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | PatchGroupScimV2GroupsGroupIdPatchResponsePatchGroupScimV2GroupsGroupIdPatch]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    group_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchGroupScimV2GroupsGroupIdPatchBody,

) -> Response[HTTPValidationError | PatchGroupScimV2GroupsGroupIdPatchResponsePatchGroupScimV2GroupsGroupIdPatch]:
    """ Patch Group

    Args:
        group_id (UUID):
        body (PatchGroupScimV2GroupsGroupIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchGroupScimV2GroupsGroupIdPatchResponsePatchGroupScimV2GroupsGroupIdPatch]
     """


    kwargs = _get_kwargs(
        group_id=group_id,
body=body,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    group_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchGroupScimV2GroupsGroupIdPatchBody,

) -> HTTPValidationError | PatchGroupScimV2GroupsGroupIdPatchResponsePatchGroupScimV2GroupsGroupIdPatch | None:
    """ Patch Group

    Args:
        group_id (UUID):
        body (PatchGroupScimV2GroupsGroupIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchGroupScimV2GroupsGroupIdPatchResponsePatchGroupScimV2GroupsGroupIdPatch
     """


    return sync_detailed(
        group_id=group_id,
client=client,
body=body,

    ).parsed

async def asyncio_detailed(
    group_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchGroupScimV2GroupsGroupIdPatchBody,

) -> Response[HTTPValidationError | PatchGroupScimV2GroupsGroupIdPatchResponsePatchGroupScimV2GroupsGroupIdPatch]:
    """ Patch Group

    Args:
        group_id (UUID):
        body (PatchGroupScimV2GroupsGroupIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchGroupScimV2GroupsGroupIdPatchResponsePatchGroupScimV2GroupsGroupIdPatch]
     """


    kwargs = _get_kwargs(
        group_id=group_id,
body=body,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    group_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchGroupScimV2GroupsGroupIdPatchBody,

) -> HTTPValidationError | PatchGroupScimV2GroupsGroupIdPatchResponsePatchGroupScimV2GroupsGroupIdPatch | None:
    """ Patch Group

    Args:
        group_id (UUID):
        body (PatchGroupScimV2GroupsGroupIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchGroupScimV2GroupsGroupIdPatchResponsePatchGroupScimV2GroupsGroupIdPatch
     """


    return (await asyncio_detailed(
        group_id=group_id,
client=client,
body=body,

    )).parsed
