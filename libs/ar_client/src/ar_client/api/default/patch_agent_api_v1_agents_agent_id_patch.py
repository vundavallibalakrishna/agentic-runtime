from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.agent_patch import AgentPatch
from ...models.http_validation_error import HTTPValidationError
from ...models.patch_agent_api_v1_agents_agent_id_patch_response_patch_agent_api_v1_agents_agent_id_patch import (
    PatchAgentApiV1AgentsAgentIdPatchResponsePatchAgentApiV1AgentsAgentIdPatch,
)
from ...types import UNSET, Response, Unset


def _get_kwargs(
    agent_id: UUID,
    *,
    body: AgentPatch,
    if_match: str | Unset | None = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(if_match, Unset):
        headers["If-Match"] = if_match

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/agents/{agent_id}".format(
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
    HTTPValidationError
    | PatchAgentApiV1AgentsAgentIdPatchResponsePatchAgentApiV1AgentsAgentIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = (
            PatchAgentApiV1AgentsAgentIdPatchResponsePatchAgentApiV1AgentsAgentIdPatch.from_dict(
                response.json()
            )
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
    HTTPValidationError | PatchAgentApiV1AgentsAgentIdPatchResponsePatchAgentApiV1AgentsAgentIdPatch
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
    body: AgentPatch,
    if_match: str | Unset | None = UNSET,
) -> Response[
    HTTPValidationError | PatchAgentApiV1AgentsAgentIdPatchResponsePatchAgentApiV1AgentsAgentIdPatch
]:
    """Patch Agent

    Args:
        agent_id (UUID):
        if_match (None | str | Unset):
        body (AgentPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchAgentApiV1AgentsAgentIdPatchResponsePatchAgentApiV1AgentsAgentIdPatch]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        body=body,
        if_match=if_match,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AgentPatch,
    if_match: str | Unset | None = UNSET,
) -> (
    HTTPValidationError
    | PatchAgentApiV1AgentsAgentIdPatchResponsePatchAgentApiV1AgentsAgentIdPatch
    | None
):
    """Patch Agent

    Args:
        agent_id (UUID):
        if_match (None | str | Unset):
        body (AgentPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchAgentApiV1AgentsAgentIdPatchResponsePatchAgentApiV1AgentsAgentIdPatch
    """

    return sync_detailed(
        agent_id=agent_id,
        client=client,
        body=body,
        if_match=if_match,
    ).parsed


async def asyncio_detailed(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AgentPatch,
    if_match: str | Unset | None = UNSET,
) -> Response[
    HTTPValidationError | PatchAgentApiV1AgentsAgentIdPatchResponsePatchAgentApiV1AgentsAgentIdPatch
]:
    """Patch Agent

    Args:
        agent_id (UUID):
        if_match (None | str | Unset):
        body (AgentPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchAgentApiV1AgentsAgentIdPatchResponsePatchAgentApiV1AgentsAgentIdPatch]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        body=body,
        if_match=if_match,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    agent_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AgentPatch,
    if_match: str | Unset | None = UNSET,
) -> (
    HTTPValidationError
    | PatchAgentApiV1AgentsAgentIdPatchResponsePatchAgentApiV1AgentsAgentIdPatch
    | None
):
    """Patch Agent

    Args:
        agent_id (UUID):
        if_match (None | str | Unset):
        body (AgentPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchAgentApiV1AgentsAgentIdPatchResponsePatchAgentApiV1AgentsAgentIdPatch
    """

    return (
        await asyncio_detailed(
            agent_id=agent_id,
            client=client,
            body=body,
            if_match=if_match,
        )
    ).parsed
