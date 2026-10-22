from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.schemas_scim_v2_schemas_get_response_schemas_scim_v2_schemas_get import (
    SchemasScimV2SchemasGetResponseSchemasScimV2SchemasGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/scim/v2/Schemas",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> SchemasScimV2SchemasGetResponseSchemasScimV2SchemasGet | None:
    if response.status_code == 200:
        response_200 = SchemasScimV2SchemasGetResponseSchemasScimV2SchemasGet.from_dict(
            response.json()
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[SchemasScimV2SchemasGetResponseSchemasScimV2SchemasGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[SchemasScimV2SchemasGetResponseSchemasScimV2SchemasGet]:
    """Schemas

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[SchemasScimV2SchemasGetResponseSchemasScimV2SchemasGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> SchemasScimV2SchemasGetResponseSchemasScimV2SchemasGet | None:
    """Schemas

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        SchemasScimV2SchemasGetResponseSchemasScimV2SchemasGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[SchemasScimV2SchemasGetResponseSchemasScimV2SchemasGet]:
    """Schemas

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[SchemasScimV2SchemasGetResponseSchemasScimV2SchemasGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> SchemasScimV2SchemasGetResponseSchemasScimV2SchemasGet | None:
    """Schemas

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        SchemasScimV2SchemasGetResponseSchemasScimV2SchemasGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
