from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_servers_api_v1_tool_servers_get_response_list_servers_api_v1_tool_servers_get import (
    ListServersApiV1ToolServersGetResponseListServersApiV1ToolServersGet,
)
from ...types import UNSET, Unset
from typing import cast


def _get_kwargs(
    *,
    q: None | str | Unset = UNSET,
    kind: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_q: None | str | Unset
    if isinstance(q, Unset):
        json_q = UNSET
    else:
        json_q = q
    params["q"] = json_q

    json_kind: None | str | Unset
    if isinstance(kind, Unset):
        json_kind = UNSET
    else:
        json_kind = kind
    params["kind"] = json_kind

    json_status: None | str | Unset
    if isinstance(status, Unset):
        json_status = UNSET
    else:
        json_status = status
    params["status"] = json_status

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/tool-servers",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListServersApiV1ToolServersGetResponseListServersApiV1ToolServersGet
    | None
):
    if response.status_code == 200:
        response_200 = (
            ListServersApiV1ToolServersGetResponseListServersApiV1ToolServersGet.from_dict(
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
    HTTPValidationError | ListServersApiV1ToolServersGetResponseListServersApiV1ToolServersGet
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
    q: None | str | Unset = UNSET,
    kind: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError | ListServersApiV1ToolServersGetResponseListServersApiV1ToolServersGet
]:
    """List Servers

    Args:
        q (None | str | Unset):
        kind (None | str | Unset):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListServersApiV1ToolServersGetResponseListServersApiV1ToolServersGet]
    """

    kwargs = _get_kwargs(
        q=q,
        kind=kind,
        status=status,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    kind: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
) -> (
    HTTPValidationError
    | ListServersApiV1ToolServersGetResponseListServersApiV1ToolServersGet
    | None
):
    """List Servers

    Args:
        q (None | str | Unset):
        kind (None | str | Unset):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListServersApiV1ToolServersGetResponseListServersApiV1ToolServersGet
    """

    return sync_detailed(
        client=client,
        q=q,
        kind=kind,
        status=status,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    kind: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError | ListServersApiV1ToolServersGetResponseListServersApiV1ToolServersGet
]:
    """List Servers

    Args:
        q (None | str | Unset):
        kind (None | str | Unset):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListServersApiV1ToolServersGetResponseListServersApiV1ToolServersGet]
    """

    kwargs = _get_kwargs(
        q=q,
        kind=kind,
        status=status,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    kind: None | str | Unset = UNSET,
    status: None | str | Unset = UNSET,
) -> (
    HTTPValidationError
    | ListServersApiV1ToolServersGetResponseListServersApiV1ToolServersGet
    | None
):
    """List Servers

    Args:
        q (None | str | Unset):
        kind (None | str | Unset):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListServersApiV1ToolServersGetResponseListServersApiV1ToolServersGet
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            kind=kind,
            status=status,
        )
    ).parsed
