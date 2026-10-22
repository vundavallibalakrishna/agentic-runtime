from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_agent_memory_api_v1_agents_agent_id_memory_get_response_list_agent_memory_api_v1_agents_agent_id_memory_get import (
    ListAgentMemoryApiV1AgentsAgentIdMemoryGetResponseListAgentMemoryApiV1AgentsAgentIdMemoryGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    agent_id: UUID,
    *,
    status: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_status: None | str | Unset
    if isinstance(status, Unset):
        json_status = UNSET
    else:
        json_status = status
    params["status"] = json_status

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/agents/{agent_id}/memory".format(
            agent_id=quote(str(agent_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListAgentMemoryApiV1AgentsAgentIdMemoryGetResponseListAgentMemoryApiV1AgentsAgentIdMemoryGet
    | None
):
    if response.status_code == 200:
        response_200 = ListAgentMemoryApiV1AgentsAgentIdMemoryGetResponseListAgentMemoryApiV1AgentsAgentIdMemoryGet.from_dict(
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
    | ListAgentMemoryApiV1AgentsAgentIdMemoryGetResponseListAgentMemoryApiV1AgentsAgentIdMemoryGet
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    status: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError
    | ListAgentMemoryApiV1AgentsAgentIdMemoryGetResponseListAgentMemoryApiV1AgentsAgentIdMemoryGet
]:
    """List Agent Memory

    Args:
        agent_id (UUID):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListAgentMemoryApiV1AgentsAgentIdMemoryGetResponseListAgentMemoryApiV1AgentsAgentIdMemoryGet]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        status=status,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    status: None | str | Unset = UNSET,
) -> (
    HTTPValidationError
    | ListAgentMemoryApiV1AgentsAgentIdMemoryGetResponseListAgentMemoryApiV1AgentsAgentIdMemoryGet
    | None
):
    """List Agent Memory

    Args:
        agent_id (UUID):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListAgentMemoryApiV1AgentsAgentIdMemoryGetResponseListAgentMemoryApiV1AgentsAgentIdMemoryGet
    """

    return sync_detailed(
        agent_id=agent_id,
        client=client,
        status=status,
    ).parsed


async def asyncio_detailed(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    status: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError
    | ListAgentMemoryApiV1AgentsAgentIdMemoryGetResponseListAgentMemoryApiV1AgentsAgentIdMemoryGet
]:
    """List Agent Memory

    Args:
        agent_id (UUID):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListAgentMemoryApiV1AgentsAgentIdMemoryGetResponseListAgentMemoryApiV1AgentsAgentIdMemoryGet]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        status=status,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    status: None | str | Unset = UNSET,
) -> (
    HTTPValidationError
    | ListAgentMemoryApiV1AgentsAgentIdMemoryGetResponseListAgentMemoryApiV1AgentsAgentIdMemoryGet
    | None
):
    """List Agent Memory

    Args:
        agent_id (UUID):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListAgentMemoryApiV1AgentsAgentIdMemoryGetResponseListAgentMemoryApiV1AgentsAgentIdMemoryGet
    """

    return (
        await asyncio_detailed(
            agent_id=agent_id,
            client=client,
            status=status,
        )
    ).parsed
