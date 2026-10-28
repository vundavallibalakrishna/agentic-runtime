from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.card_patch import CardPatch
from ...models.http_validation_error import HTTPValidationError
from ...models.patch_card_api_v1_agents_agent_id_cards_version_patch_response_patch_card_api_v1_agents_agent_id_cards_version_patch import (
    PatchCardApiV1AgentsAgentIdCardsVersionPatchResponsePatchCardApiV1AgentsAgentIdCardsVersionPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    agent_id: UUID,
    version: int,
    *,
    body: CardPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/agents/{agent_id}/cards/{version}".format(
            agent_id=quote(str(agent_id), safe=""),
            version=quote(str(version), safe=""),
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
    | PatchCardApiV1AgentsAgentIdCardsVersionPatchResponsePatchCardApiV1AgentsAgentIdCardsVersionPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchCardApiV1AgentsAgentIdCardsVersionPatchResponsePatchCardApiV1AgentsAgentIdCardsVersionPatch.from_dict(
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
    | PatchCardApiV1AgentsAgentIdCardsVersionPatchResponsePatchCardApiV1AgentsAgentIdCardsVersionPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    agent_id: UUID,
    version: int,
    *,
    client: AuthenticatedClient | Client,
    body: CardPatch,
) -> Response[
    HTTPValidationError
    | PatchCardApiV1AgentsAgentIdCardsVersionPatchResponsePatchCardApiV1AgentsAgentIdCardsVersionPatch
]:
    """Patch Card

    Args:
        agent_id (UUID):
        version (int):
        body (CardPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchCardApiV1AgentsAgentIdCardsVersionPatchResponsePatchCardApiV1AgentsAgentIdCardsVersionPatch]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        version=version,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    agent_id: UUID,
    version: int,
    *,
    client: AuthenticatedClient | Client,
    body: CardPatch,
) -> (
    HTTPValidationError
    | PatchCardApiV1AgentsAgentIdCardsVersionPatchResponsePatchCardApiV1AgentsAgentIdCardsVersionPatch
    | None
):
    """Patch Card

    Args:
        agent_id (UUID):
        version (int):
        body (CardPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchCardApiV1AgentsAgentIdCardsVersionPatchResponsePatchCardApiV1AgentsAgentIdCardsVersionPatch
    """

    return sync_detailed(
        agent_id=agent_id,
        version=version,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    agent_id: UUID,
    version: int,
    *,
    client: AuthenticatedClient | Client,
    body: CardPatch,
) -> Response[
    HTTPValidationError
    | PatchCardApiV1AgentsAgentIdCardsVersionPatchResponsePatchCardApiV1AgentsAgentIdCardsVersionPatch
]:
    """Patch Card

    Args:
        agent_id (UUID):
        version (int):
        body (CardPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchCardApiV1AgentsAgentIdCardsVersionPatchResponsePatchCardApiV1AgentsAgentIdCardsVersionPatch]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        version=version,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    agent_id: UUID,
    version: int,
    *,
    client: AuthenticatedClient | Client,
    body: CardPatch,
) -> (
    HTTPValidationError
    | PatchCardApiV1AgentsAgentIdCardsVersionPatchResponsePatchCardApiV1AgentsAgentIdCardsVersionPatch
    | None
):
    """Patch Card

    Args:
        agent_id (UUID):
        version (int):
        body (CardPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchCardApiV1AgentsAgentIdCardsVersionPatchResponsePatchCardApiV1AgentsAgentIdCardsVersionPatch
    """

    return (
        await asyncio_detailed(
            agent_id=agent_id,
            version=version,
            client=client,
            body=body,
        )
    ).parsed
