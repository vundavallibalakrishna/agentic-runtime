from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_memory_api_v1_memory_get_response_list_memory_api_v1_memory_get import (
    ListMemoryApiV1MemoryGetResponseListMemoryApiV1MemoryGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    *,
    scope: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    category: None | str | Unset = UNSET,
    q: str | Unset = "",
    status: str | Unset = "active",
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_scope: None | str | Unset
    if isinstance(scope, Unset):
        json_scope = UNSET
    else:
        json_scope = scope
    params["scope"] = json_scope

    json_agent_id: None | str | Unset
    if isinstance(agent_id, Unset):
        json_agent_id = UNSET
    elif isinstance(agent_id, UUID):
        json_agent_id = str(agent_id)
    else:
        json_agent_id = agent_id
    params["agent_id"] = json_agent_id

    json_category: None | str | Unset
    if isinstance(category, Unset):
        json_category = UNSET
    else:
        json_category = category
    params["category"] = json_category

    params["q"] = q

    params["status"] = status

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/memory",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ListMemoryApiV1MemoryGetResponseListMemoryApiV1MemoryGet | None:
    if response.status_code == 200:
        response_200 = ListMemoryApiV1MemoryGetResponseListMemoryApiV1MemoryGet.from_dict(
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
) -> Response[HTTPValidationError | ListMemoryApiV1MemoryGetResponseListMemoryApiV1MemoryGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    scope: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    category: None | str | Unset = UNSET,
    q: str | Unset = "",
    status: str | Unset = "active",
) -> Response[HTTPValidationError | ListMemoryApiV1MemoryGetResponseListMemoryApiV1MemoryGet]:
    """List Memory

    Args:
        scope (None | str | Unset):
        agent_id (None | Unset | UUID):
        category (None | str | Unset):
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: 'active'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListMemoryApiV1MemoryGetResponseListMemoryApiV1MemoryGet]
    """

    kwargs = _get_kwargs(
        scope=scope,
        agent_id=agent_id,
        category=category,
        q=q,
        status=status,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    scope: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    category: None | str | Unset = UNSET,
    q: str | Unset = "",
    status: str | Unset = "active",
) -> HTTPValidationError | ListMemoryApiV1MemoryGetResponseListMemoryApiV1MemoryGet | None:
    """List Memory

    Args:
        scope (None | str | Unset):
        agent_id (None | Unset | UUID):
        category (None | str | Unset):
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: 'active'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListMemoryApiV1MemoryGetResponseListMemoryApiV1MemoryGet
    """

    return sync_detailed(
        client=client,
        scope=scope,
        agent_id=agent_id,
        category=category,
        q=q,
        status=status,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    scope: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    category: None | str | Unset = UNSET,
    q: str | Unset = "",
    status: str | Unset = "active",
) -> Response[HTTPValidationError | ListMemoryApiV1MemoryGetResponseListMemoryApiV1MemoryGet]:
    """List Memory

    Args:
        scope (None | str | Unset):
        agent_id (None | Unset | UUID):
        category (None | str | Unset):
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: 'active'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListMemoryApiV1MemoryGetResponseListMemoryApiV1MemoryGet]
    """

    kwargs = _get_kwargs(
        scope=scope,
        agent_id=agent_id,
        category=category,
        q=q,
        status=status,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    scope: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    category: None | str | Unset = UNSET,
    q: str | Unset = "",
    status: str | Unset = "active",
) -> HTTPValidationError | ListMemoryApiV1MemoryGetResponseListMemoryApiV1MemoryGet | None:
    """List Memory

    Args:
        scope (None | str | Unset):
        agent_id (None | Unset | UUID):
        category (None | str | Unset):
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: 'active'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListMemoryApiV1MemoryGetResponseListMemoryApiV1MemoryGet
    """

    return (
        await asyncio_detailed(
            client=client,
            scope=scope,
            agent_id=agent_id,
            category=category,
            q=q,
            status=status,
        )
    ).parsed
