from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_sandbox_api_v1_sandboxes_sandbox_id_get_response_get_sandbox_api_v1_sandboxes_sandbox_id_get import (
    GetSandboxApiV1SandboxesSandboxIdGetResponseGetSandboxApiV1SandboxesSandboxIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    sandbox_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/sandboxes/{sandbox_id}".format(
            sandbox_id=quote(str(sandbox_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetSandboxApiV1SandboxesSandboxIdGetResponseGetSandboxApiV1SandboxesSandboxIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetSandboxApiV1SandboxesSandboxIdGetResponseGetSandboxApiV1SandboxesSandboxIdGet.from_dict(
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
) -> Response[
    GetSandboxApiV1SandboxesSandboxIdGetResponseGetSandboxApiV1SandboxesSandboxIdGet
    | HTTPValidationError
]:
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
) -> Response[
    GetSandboxApiV1SandboxesSandboxIdGetResponseGetSandboxApiV1SandboxesSandboxIdGet
    | HTTPValidationError
]:
    """Get Sandbox

    Args:
        sandbox_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetSandboxApiV1SandboxesSandboxIdGetResponseGetSandboxApiV1SandboxesSandboxIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        sandbox_id=sandbox_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    sandbox_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetSandboxApiV1SandboxesSandboxIdGetResponseGetSandboxApiV1SandboxesSandboxIdGet
    | HTTPValidationError
    | None
):
    """Get Sandbox

    Args:
        sandbox_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetSandboxApiV1SandboxesSandboxIdGetResponseGetSandboxApiV1SandboxesSandboxIdGet | HTTPValidationError
    """

    return sync_detailed(
        sandbox_id=sandbox_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    sandbox_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetSandboxApiV1SandboxesSandboxIdGetResponseGetSandboxApiV1SandboxesSandboxIdGet
    | HTTPValidationError
]:
    """Get Sandbox

    Args:
        sandbox_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetSandboxApiV1SandboxesSandboxIdGetResponseGetSandboxApiV1SandboxesSandboxIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        sandbox_id=sandbox_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    sandbox_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetSandboxApiV1SandboxesSandboxIdGetResponseGetSandboxApiV1SandboxesSandboxIdGet
    | HTTPValidationError
    | None
):
    """Get Sandbox

    Args:
        sandbox_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetSandboxApiV1SandboxesSandboxIdGetResponseGetSandboxApiV1SandboxesSandboxIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            sandbox_id=sandbox_id,
            client=client,
        )
    ).parsed
