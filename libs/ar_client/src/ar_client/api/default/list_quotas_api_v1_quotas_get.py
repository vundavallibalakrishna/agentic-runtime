from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_quotas_api_v1_quotas_get_response_list_quotas_api_v1_quotas_get import (
    ListQuotasApiV1QuotasGetResponseListQuotasApiV1QuotasGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/quotas",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ListQuotasApiV1QuotasGetResponseListQuotasApiV1QuotasGet | None:
    if response.status_code == 200:
        response_200 = ListQuotasApiV1QuotasGetResponseListQuotasApiV1QuotasGet.from_dict(
            response.json()
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ListQuotasApiV1QuotasGetResponseListQuotasApiV1QuotasGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListQuotasApiV1QuotasGetResponseListQuotasApiV1QuotasGet]:
    """List Quotas

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListQuotasApiV1QuotasGetResponseListQuotasApiV1QuotasGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> ListQuotasApiV1QuotasGetResponseListQuotasApiV1QuotasGet | None:
    """List Quotas

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListQuotasApiV1QuotasGetResponseListQuotasApiV1QuotasGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListQuotasApiV1QuotasGetResponseListQuotasApiV1QuotasGet]:
    """List Quotas

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListQuotasApiV1QuotasGetResponseListQuotasApiV1QuotasGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> ListQuotasApiV1QuotasGetResponseListQuotasApiV1QuotasGet | None:
    """List Quotas

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListQuotasApiV1QuotasGetResponseListQuotasApiV1QuotasGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
