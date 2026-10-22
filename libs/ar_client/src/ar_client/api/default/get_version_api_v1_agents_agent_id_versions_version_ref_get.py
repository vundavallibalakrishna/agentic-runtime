from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_version_api_v1_agents_agent_id_versions_version_ref_get_response_get_version_api_v1_agents_agent_id_versions_version_ref_get import (
    GetVersionApiV1AgentsAgentIdVersionsVersionRefGetResponseGetVersionApiV1AgentsAgentIdVersionsVersionRefGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    agent_id: UUID,
    version_ref: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/agents/{agent_id}/versions/{version_ref}".format(
            agent_id=quote(str(agent_id), safe=""),
            version_ref=quote(str(version_ref), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetVersionApiV1AgentsAgentIdVersionsVersionRefGetResponseGetVersionApiV1AgentsAgentIdVersionsVersionRefGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetVersionApiV1AgentsAgentIdVersionsVersionRefGetResponseGetVersionApiV1AgentsAgentIdVersionsVersionRefGet.from_dict(
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
    GetVersionApiV1AgentsAgentIdVersionsVersionRefGetResponseGetVersionApiV1AgentsAgentIdVersionsVersionRefGet
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
    version_ref: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetVersionApiV1AgentsAgentIdVersionsVersionRefGetResponseGetVersionApiV1AgentsAgentIdVersionsVersionRefGet
    | HTTPValidationError
]:
    """Get Version

    Args:
        agent_id (UUID):
        version_ref (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetVersionApiV1AgentsAgentIdVersionsVersionRefGetResponseGetVersionApiV1AgentsAgentIdVersionsVersionRefGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        version_ref=version_ref,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    agent_id: UUID,
    version_ref: str,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetVersionApiV1AgentsAgentIdVersionsVersionRefGetResponseGetVersionApiV1AgentsAgentIdVersionsVersionRefGet
    | HTTPValidationError
    | None
):
    """Get Version

    Args:
        agent_id (UUID):
        version_ref (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetVersionApiV1AgentsAgentIdVersionsVersionRefGetResponseGetVersionApiV1AgentsAgentIdVersionsVersionRefGet | HTTPValidationError
    """

    return sync_detailed(
        agent_id=agent_id,
        version_ref=version_ref,
        client=client,
    ).parsed


async def asyncio_detailed(
    agent_id: UUID,
    version_ref: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetVersionApiV1AgentsAgentIdVersionsVersionRefGetResponseGetVersionApiV1AgentsAgentIdVersionsVersionRefGet
    | HTTPValidationError
]:
    """Get Version

    Args:
        agent_id (UUID):
        version_ref (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetVersionApiV1AgentsAgentIdVersionsVersionRefGetResponseGetVersionApiV1AgentsAgentIdVersionsVersionRefGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        version_ref=version_ref,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    agent_id: UUID,
    version_ref: str,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetVersionApiV1AgentsAgentIdVersionsVersionRefGetResponseGetVersionApiV1AgentsAgentIdVersionsVersionRefGet
    | HTTPValidationError
    | None
):
    """Get Version

    Args:
        agent_id (UUID):
        version_ref (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetVersionApiV1AgentsAgentIdVersionsVersionRefGetResponseGetVersionApiV1AgentsAgentIdVersionsVersionRefGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            agent_id=agent_id,
            version_ref=version_ref,
            client=client,
        )
    ).parsed
