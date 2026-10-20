from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_groups_api_v1_groups_get_response_list_groups_api_v1_groups_get import ListGroupsApiV1GroupsGetResponseListGroupsApiV1GroupsGet
from ...types import UNSET, Unset
from typing import cast



def _get_kwargs(
    *,
    source: None | str | Unset = UNSET,

) -> dict[str, Any]:
    

    

    params: dict[str, Any] = {}

    json_source: None | str | Unset
    if isinstance(source, Unset):
        json_source = UNSET
    else:
        json_source = source
    params["source"] = json_source


    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}


    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/groups",
        "params": params,
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | ListGroupsApiV1GroupsGetResponseListGroupsApiV1GroupsGet | None:
    if response.status_code == 200:
        response_200 = ListGroupsApiV1GroupsGetResponseListGroupsApiV1GroupsGet.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | ListGroupsApiV1GroupsGetResponseListGroupsApiV1GroupsGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    source: None | str | Unset = UNSET,

) -> Response[HTTPValidationError | ListGroupsApiV1GroupsGetResponseListGroupsApiV1GroupsGet]:
    """ List Groups

    Args:
        source (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListGroupsApiV1GroupsGetResponseListGroupsApiV1GroupsGet]
     """


    kwargs = _get_kwargs(
        source=source,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    *,
    client: AuthenticatedClient | Client,
    source: None | str | Unset = UNSET,

) -> HTTPValidationError | ListGroupsApiV1GroupsGetResponseListGroupsApiV1GroupsGet | None:
    """ List Groups

    Args:
        source (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListGroupsApiV1GroupsGetResponseListGroupsApiV1GroupsGet
     """


    return sync_detailed(
        client=client,
source=source,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    source: None | str | Unset = UNSET,

) -> Response[HTTPValidationError | ListGroupsApiV1GroupsGetResponseListGroupsApiV1GroupsGet]:
    """ List Groups

    Args:
        source (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListGroupsApiV1GroupsGetResponseListGroupsApiV1GroupsGet]
     """


    kwargs = _get_kwargs(
        source=source,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    source: None | str | Unset = UNSET,

) -> HTTPValidationError | ListGroupsApiV1GroupsGetResponseListGroupsApiV1GroupsGet | None:
    """ List Groups

    Args:
        source (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListGroupsApiV1GroupsGetResponseListGroupsApiV1GroupsGet
     """


    return (await asyncio_detailed(
        client=client,
source=source,

    )).parsed
