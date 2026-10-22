from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.my_usage_api_v1_me_usage_get_response_my_usage_api_v1_me_usage_get import (
    MyUsageApiV1MeUsageGetResponseMyUsageApiV1MeUsageGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/me/usage",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> MyUsageApiV1MeUsageGetResponseMyUsageApiV1MeUsageGet | None:
    if response.status_code == 200:
        response_200 = MyUsageApiV1MeUsageGetResponseMyUsageApiV1MeUsageGet.from_dict(
            response.json()
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[MyUsageApiV1MeUsageGetResponseMyUsageApiV1MeUsageGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[MyUsageApiV1MeUsageGetResponseMyUsageApiV1MeUsageGet]:
    """My Usage

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[MyUsageApiV1MeUsageGetResponseMyUsageApiV1MeUsageGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> MyUsageApiV1MeUsageGetResponseMyUsageApiV1MeUsageGet | None:
    """My Usage

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        MyUsageApiV1MeUsageGetResponseMyUsageApiV1MeUsageGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[MyUsageApiV1MeUsageGetResponseMyUsageApiV1MeUsageGet]:
    """My Usage

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[MyUsageApiV1MeUsageGetResponseMyUsageApiV1MeUsageGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> MyUsageApiV1MeUsageGetResponseMyUsageApiV1MeUsageGet | None:
    """My Usage

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        MyUsageApiV1MeUsageGetResponseMyUsageApiV1MeUsageGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
