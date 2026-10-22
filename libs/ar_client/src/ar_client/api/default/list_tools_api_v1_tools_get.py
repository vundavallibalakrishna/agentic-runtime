from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_tools_api_v1_tools_get_response_list_tools_api_v1_tools_get import (
    ListToolsApiV1ToolsGetResponseListToolsApiV1ToolsGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    *,
    q: None | str | Unset = UNSET,
    server_id: None | Unset | UUID = UNSET,
    risk_class: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_q: None | str | Unset
    if isinstance(q, Unset):
        json_q = UNSET
    else:
        json_q = q
    params["q"] = json_q

    json_server_id: None | str | Unset
    if isinstance(server_id, Unset):
        json_server_id = UNSET
    elif isinstance(server_id, UUID):
        json_server_id = str(server_id)
    else:
        json_server_id = server_id
    params["server_id"] = json_server_id

    json_risk_class: None | str | Unset
    if isinstance(risk_class, Unset):
        json_risk_class = UNSET
    else:
        json_risk_class = risk_class
    params["risk_class"] = json_risk_class

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/tools",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ListToolsApiV1ToolsGetResponseListToolsApiV1ToolsGet | None:
    if response.status_code == 200:
        response_200 = ListToolsApiV1ToolsGetResponseListToolsApiV1ToolsGet.from_dict(
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
) -> Response[HTTPValidationError | ListToolsApiV1ToolsGetResponseListToolsApiV1ToolsGet]:
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
    server_id: None | Unset | UUID = UNSET,
    risk_class: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | ListToolsApiV1ToolsGetResponseListToolsApiV1ToolsGet]:
    """List Tools

    Args:
        q (None | str | Unset):
        server_id (None | Unset | UUID):
        risk_class (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListToolsApiV1ToolsGetResponseListToolsApiV1ToolsGet]
    """

    kwargs = _get_kwargs(
        q=q,
        server_id=server_id,
        risk_class=risk_class,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    server_id: None | Unset | UUID = UNSET,
    risk_class: None | str | Unset = UNSET,
) -> HTTPValidationError | ListToolsApiV1ToolsGetResponseListToolsApiV1ToolsGet | None:
    """List Tools

    Args:
        q (None | str | Unset):
        server_id (None | Unset | UUID):
        risk_class (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListToolsApiV1ToolsGetResponseListToolsApiV1ToolsGet
    """

    return sync_detailed(
        client=client,
        q=q,
        server_id=server_id,
        risk_class=risk_class,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    server_id: None | Unset | UUID = UNSET,
    risk_class: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | ListToolsApiV1ToolsGetResponseListToolsApiV1ToolsGet]:
    """List Tools

    Args:
        q (None | str | Unset):
        server_id (None | Unset | UUID):
        risk_class (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListToolsApiV1ToolsGetResponseListToolsApiV1ToolsGet]
    """

    kwargs = _get_kwargs(
        q=q,
        server_id=server_id,
        risk_class=risk_class,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    server_id: None | Unset | UUID = UNSET,
    risk_class: None | str | Unset = UNSET,
) -> HTTPValidationError | ListToolsApiV1ToolsGetResponseListToolsApiV1ToolsGet | None:
    """List Tools

    Args:
        q (None | str | Unset):
        server_id (None | Unset | UUID):
        risk_class (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListToolsApiV1ToolsGetResponseListToolsApiV1ToolsGet
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            server_id=server_id,
            risk_class=risk_class,
        )
    ).parsed
