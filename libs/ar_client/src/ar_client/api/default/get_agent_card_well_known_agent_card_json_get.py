from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_agent_card_well_known_agent_card_json_get_response_get_agent_card_well_known_agent_card_json_get import (
    GetAgentCardWellKnownAgentCardJsonGetResponseGetAgentCardWellKnownAgentCardJsonGet,
)
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Unset
from typing import cast


def _get_kwargs(
    *,
    agent: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_agent: None | str | Unset
    if isinstance(agent, Unset):
        json_agent = UNSET
    else:
        json_agent = agent
    params["agent"] = json_agent

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/.well-known/agent-card.json",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetAgentCardWellKnownAgentCardJsonGetResponseGetAgentCardWellKnownAgentCardJsonGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetAgentCardWellKnownAgentCardJsonGetResponseGetAgentCardWellKnownAgentCardJsonGet.from_dict(
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
    GetAgentCardWellKnownAgentCardJsonGetResponseGetAgentCardWellKnownAgentCardJsonGet
    | HTTPValidationError
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
    agent: None | str | Unset = UNSET,
) -> Response[
    GetAgentCardWellKnownAgentCardJsonGetResponseGetAgentCardWellKnownAgentCardJsonGet
    | HTTPValidationError
]:
    """Get Agent Card

    Args:
        agent (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetAgentCardWellKnownAgentCardJsonGetResponseGetAgentCardWellKnownAgentCardJsonGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        agent=agent,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    agent: None | str | Unset = UNSET,
) -> (
    GetAgentCardWellKnownAgentCardJsonGetResponseGetAgentCardWellKnownAgentCardJsonGet
    | HTTPValidationError
    | None
):
    """Get Agent Card

    Args:
        agent (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetAgentCardWellKnownAgentCardJsonGetResponseGetAgentCardWellKnownAgentCardJsonGet | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        agent=agent,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    agent: None | str | Unset = UNSET,
) -> Response[
    GetAgentCardWellKnownAgentCardJsonGetResponseGetAgentCardWellKnownAgentCardJsonGet
    | HTTPValidationError
]:
    """Get Agent Card

    Args:
        agent (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetAgentCardWellKnownAgentCardJsonGetResponseGetAgentCardWellKnownAgentCardJsonGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        agent=agent,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    agent: None | str | Unset = UNSET,
) -> (
    GetAgentCardWellKnownAgentCardJsonGetResponseGetAgentCardWellKnownAgentCardJsonGet
    | HTTPValidationError
    | None
):
    """Get Agent Card

    Args:
        agent (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetAgentCardWellKnownAgentCardJsonGetResponseGetAgentCardWellKnownAgentCardJsonGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            agent=agent,
        )
    ).parsed
