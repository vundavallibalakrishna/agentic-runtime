from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_sod_rules_api_v1_ext_grc_sod_rules_get_response_list_sod_rules_api_v1_ext_grc_sod_rules_get import (
    ListSodRulesApiV1ExtGrcSodRulesGetResponseListSodRulesApiV1ExtGrcSodRulesGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/sod-rules",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ListSodRulesApiV1ExtGrcSodRulesGetResponseListSodRulesApiV1ExtGrcSodRulesGet | None:
    if response.status_code == 200:
        response_200 = (
            ListSodRulesApiV1ExtGrcSodRulesGetResponseListSodRulesApiV1ExtGrcSodRulesGet.from_dict(
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
) -> Response[ListSodRulesApiV1ExtGrcSodRulesGetResponseListSodRulesApiV1ExtGrcSodRulesGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListSodRulesApiV1ExtGrcSodRulesGetResponseListSodRulesApiV1ExtGrcSodRulesGet]:
    """List Sod Rules

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListSodRulesApiV1ExtGrcSodRulesGetResponseListSodRulesApiV1ExtGrcSodRulesGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> ListSodRulesApiV1ExtGrcSodRulesGetResponseListSodRulesApiV1ExtGrcSodRulesGet | None:
    """List Sod Rules

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListSodRulesApiV1ExtGrcSodRulesGetResponseListSodRulesApiV1ExtGrcSodRulesGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListSodRulesApiV1ExtGrcSodRulesGetResponseListSodRulesApiV1ExtGrcSodRulesGet]:
    """List Sod Rules

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListSodRulesApiV1ExtGrcSodRulesGetResponseListSodRulesApiV1ExtGrcSodRulesGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> ListSodRulesApiV1ExtGrcSodRulesGetResponseListSodRulesApiV1ExtGrcSodRulesGet | None:
    """List Sod Rules

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListSodRulesApiV1ExtGrcSodRulesGetResponseListSodRulesApiV1ExtGrcSodRulesGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
