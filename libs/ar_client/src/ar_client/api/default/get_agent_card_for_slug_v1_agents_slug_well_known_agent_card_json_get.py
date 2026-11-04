from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_agent_card_for_slug_v1_agents_slug_well_known_agent_card_json_get_response_get_agent_card_for_slug_v1_agents_slug_well_known_agent_card_json_get import (
    GetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGetResponseGetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    slug: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/agents/{slug}/.well-known/agent-card.json".format(
            slug=quote(str(slug), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGetResponseGetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGetResponseGetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGet.from_dict(
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
    GetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGetResponseGetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    slug: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGetResponseGetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGet
    | HTTPValidationError
]:
    """Get Agent Card For Slug

    Args:
        slug (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGetResponseGetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        slug=slug,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    slug: str,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGetResponseGetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGet
    | HTTPValidationError
    | None
):
    """Get Agent Card For Slug

    Args:
        slug (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGetResponseGetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGet | HTTPValidationError
    """

    return sync_detailed(
        slug=slug,
        client=client,
    ).parsed


async def asyncio_detailed(
    slug: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGetResponseGetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGet
    | HTTPValidationError
]:
    """Get Agent Card For Slug

    Args:
        slug (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGetResponseGetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        slug=slug,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    slug: str,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGetResponseGetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGet
    | HTTPValidationError
    | None
):
    """Get Agent Card For Slug

    Args:
        slug (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGetResponseGetAgentCardForSlugV1AgentsSlugWellKnownAgentCardJsonGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            slug=slug,
            client=client,
        )
    ).parsed
