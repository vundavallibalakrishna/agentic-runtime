from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_memory_api_v1_memory_post_response_create_memory_api_v1_memory_post import (
    CreateMemoryApiV1MemoryPostResponseCreateMemoryApiV1MemoryPost,
)
from ...models.http_validation_error import HTTPValidationError
from ...models.memory_body import MemoryBody
from typing import cast


def _get_kwargs(
    *,
    body: MemoryBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/memory",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CreateMemoryApiV1MemoryPostResponseCreateMemoryApiV1MemoryPost | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = CreateMemoryApiV1MemoryPostResponseCreateMemoryApiV1MemoryPost.from_dict(
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
) -> Response[CreateMemoryApiV1MemoryPostResponseCreateMemoryApiV1MemoryPost | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: MemoryBody,
) -> Response[CreateMemoryApiV1MemoryPostResponseCreateMemoryApiV1MemoryPost | HTTPValidationError]:
    """Create Memory

    Args:
        body (MemoryBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateMemoryApiV1MemoryPostResponseCreateMemoryApiV1MemoryPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: MemoryBody,
) -> CreateMemoryApiV1MemoryPostResponseCreateMemoryApiV1MemoryPost | HTTPValidationError | None:
    """Create Memory

    Args:
        body (MemoryBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateMemoryApiV1MemoryPostResponseCreateMemoryApiV1MemoryPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: MemoryBody,
) -> Response[CreateMemoryApiV1MemoryPostResponseCreateMemoryApiV1MemoryPost | HTTPValidationError]:
    """Create Memory

    Args:
        body (MemoryBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateMemoryApiV1MemoryPostResponseCreateMemoryApiV1MemoryPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: MemoryBody,
) -> CreateMemoryApiV1MemoryPostResponseCreateMemoryApiV1MemoryPost | HTTPValidationError | None:
    """Create Memory

    Args:
        body (MemoryBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateMemoryApiV1MemoryPostResponseCreateMemoryApiV1MemoryPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
