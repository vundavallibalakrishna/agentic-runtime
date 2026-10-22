from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_tool_calls_api_v1_tool_calls_get_response_list_tool_calls_api_v1_tool_calls_get import (
    ListToolCallsApiV1ToolCallsGetResponseListToolCallsApiV1ToolCallsGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    *,
    run_id: None | Unset | UUID = UNSET,
    tool_id: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
    q: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_run_id: None | str | Unset
    if isinstance(run_id, Unset):
        json_run_id = UNSET
    elif isinstance(run_id, UUID):
        json_run_id = str(run_id)
    else:
        json_run_id = run_id
    params["run_id"] = json_run_id

    json_tool_id: None | str | Unset
    if isinstance(tool_id, Unset):
        json_tool_id = UNSET
    elif isinstance(tool_id, UUID):
        json_tool_id = str(tool_id)
    else:
        json_tool_id = tool_id
    params["tool_id"] = json_tool_id

    json_status: None | str | Unset
    if isinstance(status, Unset):
        json_status = UNSET
    else:
        json_status = status
    params["status"] = json_status

    json_q: None | str | Unset
    if isinstance(q, Unset):
        json_q = UNSET
    else:
        json_q = q
    params["q"] = json_q

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/tool-calls",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListToolCallsApiV1ToolCallsGetResponseListToolCallsApiV1ToolCallsGet
    | None
):
    if response.status_code == 200:
        response_200 = (
            ListToolCallsApiV1ToolCallsGetResponseListToolCallsApiV1ToolCallsGet.from_dict(
                response.json()
            )
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
    HTTPValidationError | ListToolCallsApiV1ToolCallsGetResponseListToolCallsApiV1ToolCallsGet
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
    run_id: None | Unset | UUID = UNSET,
    tool_id: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
    q: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError | ListToolCallsApiV1ToolCallsGetResponseListToolCallsApiV1ToolCallsGet
]:
    """List Tool Calls

    Args:
        run_id (None | Unset | UUID):
        tool_id (None | Unset | UUID):
        status (None | str | Unset):
        q (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListToolCallsApiV1ToolCallsGetResponseListToolCallsApiV1ToolCallsGet]
    """

    kwargs = _get_kwargs(
        run_id=run_id,
        tool_id=tool_id,
        status=status,
        q=q,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    run_id: None | Unset | UUID = UNSET,
    tool_id: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
    q: None | str | Unset = UNSET,
) -> (
    HTTPValidationError
    | ListToolCallsApiV1ToolCallsGetResponseListToolCallsApiV1ToolCallsGet
    | None
):
    """List Tool Calls

    Args:
        run_id (None | Unset | UUID):
        tool_id (None | Unset | UUID):
        status (None | str | Unset):
        q (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListToolCallsApiV1ToolCallsGetResponseListToolCallsApiV1ToolCallsGet
    """

    return sync_detailed(
        client=client,
        run_id=run_id,
        tool_id=tool_id,
        status=status,
        q=q,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    run_id: None | Unset | UUID = UNSET,
    tool_id: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
    q: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError | ListToolCallsApiV1ToolCallsGetResponseListToolCallsApiV1ToolCallsGet
]:
    """List Tool Calls

    Args:
        run_id (None | Unset | UUID):
        tool_id (None | Unset | UUID):
        status (None | str | Unset):
        q (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListToolCallsApiV1ToolCallsGetResponseListToolCallsApiV1ToolCallsGet]
    """

    kwargs = _get_kwargs(
        run_id=run_id,
        tool_id=tool_id,
        status=status,
        q=q,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    run_id: None | Unset | UUID = UNSET,
    tool_id: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
    q: None | str | Unset = UNSET,
) -> (
    HTTPValidationError
    | ListToolCallsApiV1ToolCallsGetResponseListToolCallsApiV1ToolCallsGet
    | None
):
    """List Tool Calls

    Args:
        run_id (None | Unset | UUID):
        tool_id (None | Unset | UUID):
        status (None | str | Unset):
        q (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListToolCallsApiV1ToolCallsGetResponseListToolCallsApiV1ToolCallsGet
    """

    return (
        await asyncio_detailed(
            client=client,
            run_id=run_id,
            tool_id=tool_id,
            status=status,
            q=q,
        )
    ).parsed
