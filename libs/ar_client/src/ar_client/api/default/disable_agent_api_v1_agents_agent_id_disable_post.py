from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.disable_agent_api_v1_agents_agent_id_disable_post_response_disable_agent_api_v1_agents_agent_id_disable_post import (
    DisableAgentApiV1AgentsAgentIdDisablePostResponseDisableAgentApiV1AgentsAgentIdDisablePost,
)
from ...models.disable_body import DisableBody
from ...models.http_validation_error import HTTPValidationError
from ...types import Response


def _get_kwargs(
    agent_id: UUID,
    *,
    body: DisableBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/agents/{agent_id}:disable".format(
            agent_id=quote(str(agent_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DisableAgentApiV1AgentsAgentIdDisablePostResponseDisableAgentApiV1AgentsAgentIdDisablePost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DisableAgentApiV1AgentsAgentIdDisablePostResponseDisableAgentApiV1AgentsAgentIdDisablePost.from_dict(
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
    DisableAgentApiV1AgentsAgentIdDisablePostResponseDisableAgentApiV1AgentsAgentIdDisablePost
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
    *,
    client: AuthenticatedClient | Client,
    body: DisableBody,
) -> Response[
    DisableAgentApiV1AgentsAgentIdDisablePostResponseDisableAgentApiV1AgentsAgentIdDisablePost
    | HTTPValidationError
]:
    """Disable Agent

    Args:
        agent_id (UUID):
        body (DisableBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DisableAgentApiV1AgentsAgentIdDisablePostResponseDisableAgentApiV1AgentsAgentIdDisablePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DisableBody,
) -> (
    DisableAgentApiV1AgentsAgentIdDisablePostResponseDisableAgentApiV1AgentsAgentIdDisablePost
    | HTTPValidationError
    | None
):
    """Disable Agent

    Args:
        agent_id (UUID):
        body (DisableBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DisableAgentApiV1AgentsAgentIdDisablePostResponseDisableAgentApiV1AgentsAgentIdDisablePost | HTTPValidationError
    """

    return sync_detailed(
        agent_id=agent_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DisableBody,
) -> Response[
    DisableAgentApiV1AgentsAgentIdDisablePostResponseDisableAgentApiV1AgentsAgentIdDisablePost
    | HTTPValidationError
]:
    """Disable Agent

    Args:
        agent_id (UUID):
        body (DisableBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DisableAgentApiV1AgentsAgentIdDisablePostResponseDisableAgentApiV1AgentsAgentIdDisablePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DisableBody,
) -> (
    DisableAgentApiV1AgentsAgentIdDisablePostResponseDisableAgentApiV1AgentsAgentIdDisablePost
    | HTTPValidationError
    | None
):
    """Disable Agent

    Args:
        agent_id (UUID):
        body (DisableBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DisableAgentApiV1AgentsAgentIdDisablePostResponseDisableAgentApiV1AgentsAgentIdDisablePost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            agent_id=agent_id,
            client=client,
            body=body,
        )
    ).parsed
