from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.forget_memory_api_v1_memory_delete_response_forget_memory_api_v1_memory_delete import (
    ForgetMemoryApiV1MemoryDeleteResponseForgetMemoryApiV1MemoryDelete,
)
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    *,
    agent_id: None | Unset | UUID = UNSET,
    x_confirm: None | str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(x_confirm, Unset):
        headers["x-confirm"] = x_confirm

    params: dict[str, Any] = {}

    json_agent_id: None | str | Unset
    if isinstance(agent_id, Unset):
        json_agent_id = UNSET
    elif isinstance(agent_id, UUID):
        json_agent_id = str(agent_id)
    else:
        json_agent_id = agent_id
    params["agent_id"] = json_agent_id

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/memory",
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ForgetMemoryApiV1MemoryDeleteResponseForgetMemoryApiV1MemoryDelete | HTTPValidationError | None
):
    if response.status_code == 200:
        response_200 = ForgetMemoryApiV1MemoryDeleteResponseForgetMemoryApiV1MemoryDelete.from_dict(
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
    ForgetMemoryApiV1MemoryDeleteResponseForgetMemoryApiV1MemoryDelete | HTTPValidationError
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
    agent_id: None | Unset | UUID = UNSET,
    x_confirm: None | str | Unset = UNSET,
) -> Response[
    ForgetMemoryApiV1MemoryDeleteResponseForgetMemoryApiV1MemoryDelete | HTTPValidationError
]:
    """Forget Memory

    Args:
        agent_id (None | Unset | UUID):
        x_confirm (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ForgetMemoryApiV1MemoryDeleteResponseForgetMemoryApiV1MemoryDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        x_confirm=x_confirm,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    agent_id: None | Unset | UUID = UNSET,
    x_confirm: None | str | Unset = UNSET,
) -> (
    ForgetMemoryApiV1MemoryDeleteResponseForgetMemoryApiV1MemoryDelete | HTTPValidationError | None
):
    """Forget Memory

    Args:
        agent_id (None | Unset | UUID):
        x_confirm (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ForgetMemoryApiV1MemoryDeleteResponseForgetMemoryApiV1MemoryDelete | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        agent_id=agent_id,
        x_confirm=x_confirm,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    agent_id: None | Unset | UUID = UNSET,
    x_confirm: None | str | Unset = UNSET,
) -> Response[
    ForgetMemoryApiV1MemoryDeleteResponseForgetMemoryApiV1MemoryDelete | HTTPValidationError
]:
    """Forget Memory

    Args:
        agent_id (None | Unset | UUID):
        x_confirm (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ForgetMemoryApiV1MemoryDeleteResponseForgetMemoryApiV1MemoryDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        x_confirm=x_confirm,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    agent_id: None | Unset | UUID = UNSET,
    x_confirm: None | str | Unset = UNSET,
) -> (
    ForgetMemoryApiV1MemoryDeleteResponseForgetMemoryApiV1MemoryDelete | HTTPValidationError | None
):
    """Forget Memory

    Args:
        agent_id (None | Unset | UUID):
        x_confirm (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ForgetMemoryApiV1MemoryDeleteResponseForgetMemoryApiV1MemoryDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            agent_id=agent_id,
            x_confirm=x_confirm,
        )
    ).parsed
