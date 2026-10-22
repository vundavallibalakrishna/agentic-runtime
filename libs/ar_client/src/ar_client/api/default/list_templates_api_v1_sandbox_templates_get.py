from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_templates_api_v1_sandbox_templates_get_response_list_templates_api_v1_sandbox_templates_get import (
    ListTemplatesApiV1SandboxTemplatesGetResponseListTemplatesApiV1SandboxTemplatesGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/sandbox-templates",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ListTemplatesApiV1SandboxTemplatesGetResponseListTemplatesApiV1SandboxTemplatesGet | None:
    if response.status_code == 200:
        response_200 = ListTemplatesApiV1SandboxTemplatesGetResponseListTemplatesApiV1SandboxTemplatesGet.from_dict(
            response.json()
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ListTemplatesApiV1SandboxTemplatesGetResponseListTemplatesApiV1SandboxTemplatesGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListTemplatesApiV1SandboxTemplatesGetResponseListTemplatesApiV1SandboxTemplatesGet]:
    """List Templates

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListTemplatesApiV1SandboxTemplatesGetResponseListTemplatesApiV1SandboxTemplatesGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> ListTemplatesApiV1SandboxTemplatesGetResponseListTemplatesApiV1SandboxTemplatesGet | None:
    """List Templates

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListTemplatesApiV1SandboxTemplatesGetResponseListTemplatesApiV1SandboxTemplatesGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListTemplatesApiV1SandboxTemplatesGetResponseListTemplatesApiV1SandboxTemplatesGet]:
    """List Templates

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListTemplatesApiV1SandboxTemplatesGetResponseListTemplatesApiV1SandboxTemplatesGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> ListTemplatesApiV1SandboxTemplatesGetResponseListTemplatesApiV1SandboxTemplatesGet | None:
    """List Templates

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListTemplatesApiV1SandboxTemplatesGetResponseListTemplatesApiV1SandboxTemplatesGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
