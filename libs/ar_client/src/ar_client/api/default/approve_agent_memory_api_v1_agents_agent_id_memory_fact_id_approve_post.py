from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.approve_agent_memory_api_v1_agents_agent_id_memory_fact_id_approve_post_response_approve_agent_memory_api_v1_agents_agent_id_memory_fact_id_approve_post import (
    ApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePostResponseApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    agent_id: UUID,
    fact_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/agents/{agent_id}/memory/{fact_id}:approve".format(
            agent_id=quote(str(agent_id), safe=""),
            fact_id=quote(str(fact_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePostResponseApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = ApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePostResponseApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePost.from_dict(
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
    ApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePostResponseApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    agent_id: UUID,
    fact_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePostResponseApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePost
    | HTTPValidationError
]:
    """Approve Agent Memory

    Args:
        agent_id (UUID):
        fact_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePostResponseApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        fact_id=fact_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    agent_id: UUID,
    fact_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    ApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePostResponseApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePost
    | HTTPValidationError
    | None
):
    """Approve Agent Memory

    Args:
        agent_id (UUID):
        fact_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePostResponseApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePost | HTTPValidationError
    """

    return sync_detailed(
        agent_id=agent_id,
        fact_id=fact_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    agent_id: UUID,
    fact_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePostResponseApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePost
    | HTTPValidationError
]:
    """Approve Agent Memory

    Args:
        agent_id (UUID):
        fact_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePostResponseApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        fact_id=fact_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    agent_id: UUID,
    fact_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    ApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePostResponseApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePost
    | HTTPValidationError
    | None
):
    """Approve Agent Memory

    Args:
        agent_id (UUID):
        fact_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePostResponseApproveAgentMemoryApiV1AgentsAgentIdMemoryFactIdApprovePost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            agent_id=agent_id,
            fact_id=fact_id,
            client=client,
        )
    ).parsed
