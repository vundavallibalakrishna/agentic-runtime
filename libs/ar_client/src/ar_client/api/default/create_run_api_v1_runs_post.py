from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_run_api_v1_runs_post_response_create_run_api_v1_runs_post import (
    CreateRunApiV1RunsPostResponseCreateRunApiV1RunsPost,
)
from ...models.http_validation_error import HTTPValidationError
from ...models.run_body import RunBody
from typing import cast


def _get_kwargs(
    *,
    body: RunBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/runs",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CreateRunApiV1RunsPostResponseCreateRunApiV1RunsPost | HTTPValidationError | None:
    if response.status_code == 202:
        response_202 = CreateRunApiV1RunsPostResponseCreateRunApiV1RunsPost.from_dict(
            response.json()
        )

        return response_202

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[CreateRunApiV1RunsPostResponseCreateRunApiV1RunsPost | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: RunBody,
) -> Response[CreateRunApiV1RunsPostResponseCreateRunApiV1RunsPost | HTTPValidationError]:
    """Create Run

    Args:
        body (RunBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateRunApiV1RunsPostResponseCreateRunApiV1RunsPost | HTTPValidationError]
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
    body: RunBody,
) -> CreateRunApiV1RunsPostResponseCreateRunApiV1RunsPost | HTTPValidationError | None:
    """Create Run

    Args:
        body (RunBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateRunApiV1RunsPostResponseCreateRunApiV1RunsPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: RunBody,
) -> Response[CreateRunApiV1RunsPostResponseCreateRunApiV1RunsPost | HTTPValidationError]:
    """Create Run

    Args:
        body (RunBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateRunApiV1RunsPostResponseCreateRunApiV1RunsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: RunBody,
) -> CreateRunApiV1RunsPostResponseCreateRunApiV1RunsPost | HTTPValidationError | None:
    """Create Run

    Args:
        body (RunBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateRunApiV1RunsPostResponseCreateRunApiV1RunsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
