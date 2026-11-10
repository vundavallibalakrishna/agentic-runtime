from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.guest_agent_turn_api_v1_guest_agents_agent_id_turns_post_response_guest_agent_turn_api_v1_guest_agents_agent_id_turns_post import (
    GuestAgentTurnApiV1GuestAgentsAgentIdTurnsPostResponseGuestAgentTurnApiV1GuestAgentsAgentIdTurnsPost,
)
from ...models.guest_turn_body import GuestTurnBody
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    agent_id: UUID,
    *,
    body: GuestTurnBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/guest/agents/{agent_id}/turns".format(
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
    GuestAgentTurnApiV1GuestAgentsAgentIdTurnsPostResponseGuestAgentTurnApiV1GuestAgentsAgentIdTurnsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GuestAgentTurnApiV1GuestAgentsAgentIdTurnsPostResponseGuestAgentTurnApiV1GuestAgentsAgentIdTurnsPost.from_dict(
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
    GuestAgentTurnApiV1GuestAgentsAgentIdTurnsPostResponseGuestAgentTurnApiV1GuestAgentsAgentIdTurnsPost
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
    body: GuestTurnBody,
) -> Response[
    GuestAgentTurnApiV1GuestAgentsAgentIdTurnsPostResponseGuestAgentTurnApiV1GuestAgentsAgentIdTurnsPost
    | HTTPValidationError
]:
    """Guest Agent Turn

    Args:
        agent_id (UUID):
        body (GuestTurnBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GuestAgentTurnApiV1GuestAgentsAgentIdTurnsPostResponseGuestAgentTurnApiV1GuestAgentsAgentIdTurnsPost | HTTPValidationError]
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
    body: GuestTurnBody,
) -> (
    GuestAgentTurnApiV1GuestAgentsAgentIdTurnsPostResponseGuestAgentTurnApiV1GuestAgentsAgentIdTurnsPost
    | HTTPValidationError
    | None
):
    """Guest Agent Turn

    Args:
        agent_id (UUID):
        body (GuestTurnBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GuestAgentTurnApiV1GuestAgentsAgentIdTurnsPostResponseGuestAgentTurnApiV1GuestAgentsAgentIdTurnsPost | HTTPValidationError
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
    body: GuestTurnBody,
) -> Response[
    GuestAgentTurnApiV1GuestAgentsAgentIdTurnsPostResponseGuestAgentTurnApiV1GuestAgentsAgentIdTurnsPost
    | HTTPValidationError
]:
    """Guest Agent Turn

    Args:
        agent_id (UUID):
        body (GuestTurnBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GuestAgentTurnApiV1GuestAgentsAgentIdTurnsPostResponseGuestAgentTurnApiV1GuestAgentsAgentIdTurnsPost | HTTPValidationError]
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
    body: GuestTurnBody,
) -> (
    GuestAgentTurnApiV1GuestAgentsAgentIdTurnsPostResponseGuestAgentTurnApiV1GuestAgentsAgentIdTurnsPost
    | HTTPValidationError
    | None
):
    """Guest Agent Turn

    Args:
        agent_id (UUID):
        body (GuestTurnBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GuestAgentTurnApiV1GuestAgentsAgentIdTurnsPostResponseGuestAgentTurnApiV1GuestAgentsAgentIdTurnsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            agent_id=agent_id,
            client=client,
            body=body,
        )
    ).parsed
