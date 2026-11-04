from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.revoke_agent_key_api_v1_agents_agent_id_api_keys_key_id_delete_response_revoke_agent_key_api_v1_agents_agent_id_api_keys_key_id_delete import (
    RevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDeleteResponseRevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDelete,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    agent_id: UUID,
    key_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/agents/{agent_id}/api-keys/{key_id}".format(
            agent_id=quote(str(agent_id), safe=""),
            key_id=quote(str(key_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | RevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDeleteResponseRevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDelete
    | None
):
    if response.status_code == 200:
        response_200 = RevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDeleteResponseRevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDelete.from_dict(
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
    | RevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDeleteResponseRevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDelete
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    agent_id: UUID,
    key_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDeleteResponseRevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDelete
]:
    """Revoke Agent Key

    Args:
        agent_id (UUID):
        key_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDeleteResponseRevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDelete]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        key_id=key_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    agent_id: UUID,
    key_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDeleteResponseRevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDelete
    | None
):
    """Revoke Agent Key

    Args:
        agent_id (UUID):
        key_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDeleteResponseRevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDelete
    """

    return sync_detailed(
        agent_id=agent_id,
        key_id=key_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    agent_id: UUID,
    key_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDeleteResponseRevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDelete
]:
    """Revoke Agent Key

    Args:
        agent_id (UUID):
        key_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDeleteResponseRevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDelete]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        key_id=key_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    agent_id: UUID,
    key_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDeleteResponseRevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDelete
    | None
):
    """Revoke Agent Key

    Args:
        agent_id (UUID):
        key_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDeleteResponseRevokeAgentKeyApiV1AgentsAgentIdApiKeysKeyIdDelete
    """

    return (
        await asyncio_detailed(
            agent_id=agent_id,
            key_id=key_id,
            client=client,
        )
    ).parsed
