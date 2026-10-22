from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.enable_tool_api_v1_tools_tool_id_enable_post_response_enable_tool_api_v1_tools_tool_id_enable_post import (
    EnableToolApiV1ToolsToolIdEnablePostResponseEnableToolApiV1ToolsToolIdEnablePost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    tool_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/tools/{tool_id}:enable".format(
            tool_id=quote(str(tool_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    EnableToolApiV1ToolsToolIdEnablePostResponseEnableToolApiV1ToolsToolIdEnablePost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = EnableToolApiV1ToolsToolIdEnablePostResponseEnableToolApiV1ToolsToolIdEnablePost.from_dict(
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
    EnableToolApiV1ToolsToolIdEnablePostResponseEnableToolApiV1ToolsToolIdEnablePost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    tool_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    EnableToolApiV1ToolsToolIdEnablePostResponseEnableToolApiV1ToolsToolIdEnablePost
    | HTTPValidationError
]:
    """Enable Tool

    Args:
        tool_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[EnableToolApiV1ToolsToolIdEnablePostResponseEnableToolApiV1ToolsToolIdEnablePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        tool_id=tool_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    tool_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    EnableToolApiV1ToolsToolIdEnablePostResponseEnableToolApiV1ToolsToolIdEnablePost
    | HTTPValidationError
    | None
):
    """Enable Tool

    Args:
        tool_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        EnableToolApiV1ToolsToolIdEnablePostResponseEnableToolApiV1ToolsToolIdEnablePost | HTTPValidationError
    """

    return sync_detailed(
        tool_id=tool_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    tool_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    EnableToolApiV1ToolsToolIdEnablePostResponseEnableToolApiV1ToolsToolIdEnablePost
    | HTTPValidationError
]:
    """Enable Tool

    Args:
        tool_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[EnableToolApiV1ToolsToolIdEnablePostResponseEnableToolApiV1ToolsToolIdEnablePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        tool_id=tool_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    tool_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    EnableToolApiV1ToolsToolIdEnablePostResponseEnableToolApiV1ToolsToolIdEnablePost
    | HTTPValidationError
    | None
):
    """Enable Tool

    Args:
        tool_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        EnableToolApiV1ToolsToolIdEnablePostResponseEnableToolApiV1ToolsToolIdEnablePost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            tool_id=tool_id,
            client=client,
        )
    ).parsed
