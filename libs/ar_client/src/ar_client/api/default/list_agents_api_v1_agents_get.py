from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_agents_api_v1_agents_get_response_list_agents_api_v1_agents_get import (
    ListAgentsApiV1AgentsGetResponseListAgentsApiV1AgentsGet,
)
from ...types import UNSET, Unset
from typing import cast


def _get_kwargs(
    *,
    q: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
    visibility: None | str | Unset = UNSET,
    owner: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_q: None | str | Unset
    if isinstance(q, Unset):
        json_q = UNSET
    else:
        json_q = q
    params["q"] = json_q

    json_status: None | str | Unset
    if isinstance(status, Unset):
        json_status = UNSET
    else:
        json_status = status
    params["status"] = json_status

    json_visibility: None | str | Unset
    if isinstance(visibility, Unset):
        json_visibility = UNSET
    else:
        json_visibility = visibility
    params["visibility"] = json_visibility

    json_owner: None | str | Unset
    if isinstance(owner, Unset):
        json_owner = UNSET
    else:
        json_owner = owner
    params["owner"] = json_owner

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/agents",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ListAgentsApiV1AgentsGetResponseListAgentsApiV1AgentsGet | None:
    if response.status_code == 200:
        response_200 = ListAgentsApiV1AgentsGetResponseListAgentsApiV1AgentsGet.from_dict(
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
) -> Response[HTTPValidationError | ListAgentsApiV1AgentsGetResponseListAgentsApiV1AgentsGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
    visibility: None | str | Unset = UNSET,
    owner: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | ListAgentsApiV1AgentsGetResponseListAgentsApiV1AgentsGet]:
    """List Agents

    Args:
        q (None | str | Unset):
        status (None | str | Unset):
        visibility (None | str | Unset):
        owner (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListAgentsApiV1AgentsGetResponseListAgentsApiV1AgentsGet]
    """

    kwargs = _get_kwargs(
        q=q,
        status=status,
        visibility=visibility,
        owner=owner,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
    visibility: None | str | Unset = UNSET,
    owner: None | str | Unset = UNSET,
) -> HTTPValidationError | ListAgentsApiV1AgentsGetResponseListAgentsApiV1AgentsGet | None:
    """List Agents

    Args:
        q (None | str | Unset):
        status (None | str | Unset):
        visibility (None | str | Unset):
        owner (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListAgentsApiV1AgentsGetResponseListAgentsApiV1AgentsGet
    """

    return sync_detailed(
        client=client,
        q=q,
        status=status,
        visibility=visibility,
        owner=owner,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
    visibility: None | str | Unset = UNSET,
    owner: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | ListAgentsApiV1AgentsGetResponseListAgentsApiV1AgentsGet]:
    """List Agents

    Args:
        q (None | str | Unset):
        status (None | str | Unset):
        visibility (None | str | Unset):
        owner (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListAgentsApiV1AgentsGetResponseListAgentsApiV1AgentsGet]
    """

    kwargs = _get_kwargs(
        q=q,
        status=status,
        visibility=visibility,
        owner=owner,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
    visibility: None | str | Unset = UNSET,
    owner: None | str | Unset = UNSET,
) -> HTTPValidationError | ListAgentsApiV1AgentsGetResponseListAgentsApiV1AgentsGet | None:
    """List Agents

    Args:
        q (None | str | Unset):
        status (None | str | Unset):
        visibility (None | str | Unset):
        owner (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListAgentsApiV1AgentsGetResponseListAgentsApiV1AgentsGet
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            status=status,
            visibility=visibility,
            owner=owner,
        )
    ).parsed
