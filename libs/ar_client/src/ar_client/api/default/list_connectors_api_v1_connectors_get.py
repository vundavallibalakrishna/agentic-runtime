from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_connectors_api_v1_connectors_get_response_list_connectors_api_v1_connectors_get import (
    ListConnectorsApiV1ConnectorsGetResponseListConnectorsApiV1ConnectorsGet,
)
from ...types import UNSET, Unset
from typing import cast


def _get_kwargs(
    *,
    q: str | Unset = "",
    category: str | Unset = "",
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

    params["category"] = category

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/connectors",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListConnectorsApiV1ConnectorsGetResponseListConnectorsApiV1ConnectorsGet
    | None
):
    if response.status_code == 200:
        response_200 = (
            ListConnectorsApiV1ConnectorsGetResponseListConnectorsApiV1ConnectorsGet.from_dict(
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
    HTTPValidationError | ListConnectorsApiV1ConnectorsGetResponseListConnectorsApiV1ConnectorsGet
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
    q: str | Unset = "",
    category: str | Unset = "",
) -> Response[
    HTTPValidationError | ListConnectorsApiV1ConnectorsGetResponseListConnectorsApiV1ConnectorsGet
]:
    """List Connectors

    Args:
        q (str | Unset):  Default: ''.
        category (str | Unset):  Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListConnectorsApiV1ConnectorsGetResponseListConnectorsApiV1ConnectorsGet]
    """

    kwargs = _get_kwargs(
        q=q,
        category=category,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    category: str | Unset = "",
) -> (
    HTTPValidationError
    | ListConnectorsApiV1ConnectorsGetResponseListConnectorsApiV1ConnectorsGet
    | None
):
    """List Connectors

    Args:
        q (str | Unset):  Default: ''.
        category (str | Unset):  Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListConnectorsApiV1ConnectorsGetResponseListConnectorsApiV1ConnectorsGet
    """

    return sync_detailed(
        client=client,
        q=q,
        category=category,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    category: str | Unset = "",
) -> Response[
    HTTPValidationError | ListConnectorsApiV1ConnectorsGetResponseListConnectorsApiV1ConnectorsGet
]:
    """List Connectors

    Args:
        q (str | Unset):  Default: ''.
        category (str | Unset):  Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListConnectorsApiV1ConnectorsGetResponseListConnectorsApiV1ConnectorsGet]
    """

    kwargs = _get_kwargs(
        q=q,
        category=category,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    category: str | Unset = "",
) -> (
    HTTPValidationError
    | ListConnectorsApiV1ConnectorsGetResponseListConnectorsApiV1ConnectorsGet
    | None
):
    """List Connectors

    Args:
        q (str | Unset):  Default: ''.
        category (str | Unset):  Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListConnectorsApiV1ConnectorsGetResponseListConnectorsApiV1ConnectorsGet
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            category=category,
        )
    ).parsed
