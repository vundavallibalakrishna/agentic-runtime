from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.list_packs_api_v1_content_packs_get_response_list_packs_api_v1_content_packs_get import (
    ListPacksApiV1ContentPacksGetResponseListPacksApiV1ContentPacksGet,
)
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/content-packs",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ListPacksApiV1ContentPacksGetResponseListPacksApiV1ContentPacksGet | None:
    if response.status_code == 200:
        response_200 = ListPacksApiV1ContentPacksGetResponseListPacksApiV1ContentPacksGet.from_dict(
            response.json()
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ListPacksApiV1ContentPacksGetResponseListPacksApiV1ContentPacksGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListPacksApiV1ContentPacksGetResponseListPacksApiV1ContentPacksGet]:
    """List Packs

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListPacksApiV1ContentPacksGetResponseListPacksApiV1ContentPacksGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> ListPacksApiV1ContentPacksGetResponseListPacksApiV1ContentPacksGet | None:
    """List Packs

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListPacksApiV1ContentPacksGetResponseListPacksApiV1ContentPacksGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListPacksApiV1ContentPacksGetResponseListPacksApiV1ContentPacksGet]:
    """List Packs

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListPacksApiV1ContentPacksGetResponseListPacksApiV1ContentPacksGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> ListPacksApiV1ContentPacksGetResponseListPacksApiV1ContentPacksGet | None:
    """List Packs

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListPacksApiV1ContentPacksGetResponseListPacksApiV1ContentPacksGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
