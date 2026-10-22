from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.unarchive_agent_api_v1_agents_agent_id_unarchive_post_response_unarchive_agent_api_v1_agents_agent_id_unarchive_post import (
    UnarchiveAgentApiV1AgentsAgentIdUnarchivePostResponseUnarchiveAgentApiV1AgentsAgentIdUnarchivePost,
)
from ...types import Response


def _get_kwargs(
    agent_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/agents/{agent_id}:unarchive".format(
            agent_id=quote(str(agent_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | UnarchiveAgentApiV1AgentsAgentIdUnarchivePostResponseUnarchiveAgentApiV1AgentsAgentIdUnarchivePost
    | None
):
    if response.status_code == 200:
        response_200 = UnarchiveAgentApiV1AgentsAgentIdUnarchivePostResponseUnarchiveAgentApiV1AgentsAgentIdUnarchivePost.from_dict(
            response.json()
        )

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    HTTPValidationError
    | UnarchiveAgentApiV1AgentsAgentIdUnarchivePostResponseUnarchiveAgentApiV1AgentsAgentIdUnarchivePost
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
) -> Response[
    HTTPValidationError
    | UnarchiveAgentApiV1AgentsAgentIdUnarchivePostResponseUnarchiveAgentApiV1AgentsAgentIdUnarchivePost
]:
    """Unarchive Agent

    Args:
        agent_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UnarchiveAgentApiV1AgentsAgentIdUnarchivePostResponseUnarchiveAgentApiV1AgentsAgentIdUnarchivePost]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | UnarchiveAgentApiV1AgentsAgentIdUnarchivePostResponseUnarchiveAgentApiV1AgentsAgentIdUnarchivePost
    | None
):
    """Unarchive Agent

    Args:
        agent_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UnarchiveAgentApiV1AgentsAgentIdUnarchivePostResponseUnarchiveAgentApiV1AgentsAgentIdUnarchivePost
    """

    return sync_detailed(
        agent_id=agent_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | UnarchiveAgentApiV1AgentsAgentIdUnarchivePostResponseUnarchiveAgentApiV1AgentsAgentIdUnarchivePost
]:
    """Unarchive Agent

    Args:
        agent_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UnarchiveAgentApiV1AgentsAgentIdUnarchivePostResponseUnarchiveAgentApiV1AgentsAgentIdUnarchivePost]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | UnarchiveAgentApiV1AgentsAgentIdUnarchivePostResponseUnarchiveAgentApiV1AgentsAgentIdUnarchivePost
    | None
):
    """Unarchive Agent

    Args:
        agent_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UnarchiveAgentApiV1AgentsAgentIdUnarchivePostResponseUnarchiveAgentApiV1AgentsAgentIdUnarchivePost
    """

    return (
        await asyncio_detailed(
            agent_id=agent_id,
            client=client,
        )
    ).parsed
