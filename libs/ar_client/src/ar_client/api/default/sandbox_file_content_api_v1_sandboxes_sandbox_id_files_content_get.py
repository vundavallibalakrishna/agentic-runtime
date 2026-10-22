from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    sandbox_id: UUID,
    *,
    path: str | Unset = "/workspace",
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["path"] = path

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/sandboxes/{sandbox_id}/files/content".format(
            sandbox_id=quote(str(sandbox_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = response.json()
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
) -> Response[Any | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    sandbox_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    path: str | Unset = "/workspace",
) -> Response[Any | HTTPValidationError]:
    """Sandbox File Content

    Args:
        sandbox_id (UUID):
        path (str | Unset):  Default: '/workspace'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        sandbox_id=sandbox_id,
        path=path,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    sandbox_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    path: str | Unset = "/workspace",
) -> Any | HTTPValidationError | None:
    """Sandbox File Content

    Args:
        sandbox_id (UUID):
        path (str | Unset):  Default: '/workspace'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return sync_detailed(
        sandbox_id=sandbox_id,
        client=client,
        path=path,
    ).parsed


async def asyncio_detailed(
    sandbox_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    path: str | Unset = "/workspace",
) -> Response[Any | HTTPValidationError]:
    """Sandbox File Content

    Args:
        sandbox_id (UUID):
        path (str | Unset):  Default: '/workspace'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        sandbox_id=sandbox_id,
        path=path,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    sandbox_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    path: str | Unset = "/workspace",
) -> Any | HTTPValidationError | None:
    """Sandbox File Content

    Args:
        sandbox_id (UUID):
        path (str | Unset):  Default: '/workspace'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            sandbox_id=sandbox_id,
            client=client,
            path=path,
        )
    ).parsed
