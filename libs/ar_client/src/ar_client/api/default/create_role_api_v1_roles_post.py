from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_role_api_v1_roles_post_response_create_role_api_v1_roles_post import CreateRoleApiV1RolesPostResponseCreateRoleApiV1RolesPost
from ...models.http_validation_error import HTTPValidationError
from ...models.role_create import RoleCreate
from typing import cast



def _get_kwargs(
    *,
    body: RoleCreate,

) -> dict[str, Any]:
    headers: dict[str, Any] = {}


    

    

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/roles",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> CreateRoleApiV1RolesPostResponseCreateRoleApiV1RolesPost | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = CreateRoleApiV1RolesPostResponseCreateRoleApiV1RolesPost.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[CreateRoleApiV1RolesPostResponseCreateRoleApiV1RolesPost | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: RoleCreate,

) -> Response[CreateRoleApiV1RolesPostResponseCreateRoleApiV1RolesPost | HTTPValidationError]:
    """ Create Role

    Args:
        body (RoleCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateRoleApiV1RolesPostResponseCreateRoleApiV1RolesPost | HTTPValidationError]
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
    body: RoleCreate,

) -> CreateRoleApiV1RolesPostResponseCreateRoleApiV1RolesPost | HTTPValidationError | None:
    """ Create Role

    Args:
        body (RoleCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateRoleApiV1RolesPostResponseCreateRoleApiV1RolesPost | HTTPValidationError
     """


    return sync_detailed(
        client=client,
body=body,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: RoleCreate,

) -> Response[CreateRoleApiV1RolesPostResponseCreateRoleApiV1RolesPost | HTTPValidationError]:
    """ Create Role

    Args:
        body (RoleCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateRoleApiV1RolesPostResponseCreateRoleApiV1RolesPost | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        body=body,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: RoleCreate,

) -> CreateRoleApiV1RolesPostResponseCreateRoleApiV1RolesPost | HTTPValidationError | None:
    """ Create Role

    Args:
        body (RoleCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateRoleApiV1RolesPostResponseCreateRoleApiV1RolesPost | HTTPValidationError
     """


    return (await asyncio_detailed(
        client=client,
body=body,

    )).parsed
