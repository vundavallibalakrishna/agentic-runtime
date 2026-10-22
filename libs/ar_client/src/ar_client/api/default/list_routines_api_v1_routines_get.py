from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_routines_api_v1_routines_get_response_list_routines_api_v1_routines_get import (
    ListRoutinesApiV1RoutinesGetResponseListRoutinesApiV1RoutinesGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    *,
    q: str | Unset = "",
    status: str | Unset = "",
    owner: str | Unset = "",
    agent_id: None | Unset | UUID = UNSET,
    trigger_type: str | Unset = "",
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

    params["status"] = status

    params["owner"] = owner

    json_agent_id: None | str | Unset
    if isinstance(agent_id, Unset):
        json_agent_id = UNSET
    elif isinstance(agent_id, UUID):
        json_agent_id = str(agent_id)
    else:
        json_agent_id = agent_id
    params["agent_id"] = json_agent_id

    params["trigger_type"] = trigger_type

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/routines",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ListRoutinesApiV1RoutinesGetResponseListRoutinesApiV1RoutinesGet | None:
    if response.status_code == 200:
        response_200 = ListRoutinesApiV1RoutinesGetResponseListRoutinesApiV1RoutinesGet.from_dict(
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
    HTTPValidationError | ListRoutinesApiV1RoutinesGetResponseListRoutinesApiV1RoutinesGet
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
    q: str | Unset = "",
    status: str | Unset = "",
    owner: str | Unset = "",
    agent_id: None | Unset | UUID = UNSET,
    trigger_type: str | Unset = "",
) -> Response[
    HTTPValidationError | ListRoutinesApiV1RoutinesGetResponseListRoutinesApiV1RoutinesGet
]:
    """List Routines

    Args:
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: ''.
        owner (str | Unset):  Default: ''.
        agent_id (None | Unset | UUID):
        trigger_type (str | Unset):  Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListRoutinesApiV1RoutinesGetResponseListRoutinesApiV1RoutinesGet]
    """

    kwargs = _get_kwargs(
        q=q,
        status=status,
        owner=owner,
        agent_id=agent_id,
        trigger_type=trigger_type,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: str | Unset = "",
    owner: str | Unset = "",
    agent_id: None | Unset | UUID = UNSET,
    trigger_type: str | Unset = "",
) -> HTTPValidationError | ListRoutinesApiV1RoutinesGetResponseListRoutinesApiV1RoutinesGet | None:
    """List Routines

    Args:
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: ''.
        owner (str | Unset):  Default: ''.
        agent_id (None | Unset | UUID):
        trigger_type (str | Unset):  Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListRoutinesApiV1RoutinesGetResponseListRoutinesApiV1RoutinesGet
    """

    return sync_detailed(
        client=client,
        q=q,
        status=status,
        owner=owner,
        agent_id=agent_id,
        trigger_type=trigger_type,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: str | Unset = "",
    owner: str | Unset = "",
    agent_id: None | Unset | UUID = UNSET,
    trigger_type: str | Unset = "",
) -> Response[
    HTTPValidationError | ListRoutinesApiV1RoutinesGetResponseListRoutinesApiV1RoutinesGet
]:
    """List Routines

    Args:
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: ''.
        owner (str | Unset):  Default: ''.
        agent_id (None | Unset | UUID):
        trigger_type (str | Unset):  Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListRoutinesApiV1RoutinesGetResponseListRoutinesApiV1RoutinesGet]
    """

    kwargs = _get_kwargs(
        q=q,
        status=status,
        owner=owner,
        agent_id=agent_id,
        trigger_type=trigger_type,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: str | Unset = "",
    owner: str | Unset = "",
    agent_id: None | Unset | UUID = UNSET,
    trigger_type: str | Unset = "",
) -> HTTPValidationError | ListRoutinesApiV1RoutinesGetResponseListRoutinesApiV1RoutinesGet | None:
    """List Routines

    Args:
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: ''.
        owner (str | Unset):  Default: ''.
        agent_id (None | Unset | UUID):
        trigger_type (str | Unset):  Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListRoutinesApiV1RoutinesGetResponseListRoutinesApiV1RoutinesGet
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            status=status,
            owner=owner,
            agent_id=agent_id,
            trigger_type=trigger_type,
        )
    ).parsed
