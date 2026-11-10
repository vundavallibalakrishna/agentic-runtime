from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_model_routes_api_v1_model_routes_get_response_list_model_routes_api_v1_model_routes_get import (
    ListModelRoutesApiV1ModelRoutesGetResponseListModelRoutesApiV1ModelRoutesGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/model-routes",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ListModelRoutesApiV1ModelRoutesGetResponseListModelRoutesApiV1ModelRoutesGet | None:
    if response.status_code == 200:
        response_200 = (
            ListModelRoutesApiV1ModelRoutesGetResponseListModelRoutesApiV1ModelRoutesGet.from_dict(
                response.json()
            )
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ListModelRoutesApiV1ModelRoutesGetResponseListModelRoutesApiV1ModelRoutesGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListModelRoutesApiV1ModelRoutesGetResponseListModelRoutesApiV1ModelRoutesGet]:
    """List Model Routes

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListModelRoutesApiV1ModelRoutesGetResponseListModelRoutesApiV1ModelRoutesGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> ListModelRoutesApiV1ModelRoutesGetResponseListModelRoutesApiV1ModelRoutesGet | None:
    """List Model Routes

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListModelRoutesApiV1ModelRoutesGetResponseListModelRoutesApiV1ModelRoutesGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListModelRoutesApiV1ModelRoutesGetResponseListModelRoutesApiV1ModelRoutesGet]:
    """List Model Routes

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListModelRoutesApiV1ModelRoutesGetResponseListModelRoutesApiV1ModelRoutesGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> ListModelRoutesApiV1ModelRoutesGetResponseListModelRoutesApiV1ModelRoutesGet | None:
    """List Model Routes

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListModelRoutesApiV1ModelRoutesGetResponseListModelRoutesApiV1ModelRoutesGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
