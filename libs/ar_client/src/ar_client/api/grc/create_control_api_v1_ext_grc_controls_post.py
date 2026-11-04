from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_control_api_v1_ext_grc_controls_post_body import (
    CreateControlApiV1ExtGrcControlsPostBody,
)
from ...models.create_control_api_v1_ext_grc_controls_post_response_create_control_api_v1_ext_grc_controls_post import (
    CreateControlApiV1ExtGrcControlsPostResponseCreateControlApiV1ExtGrcControlsPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    *,
    body: CreateControlApiV1ExtGrcControlsPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/controls",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateControlApiV1ExtGrcControlsPostResponseCreateControlApiV1ExtGrcControlsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CreateControlApiV1ExtGrcControlsPostResponseCreateControlApiV1ExtGrcControlsPost.from_dict(
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
    CreateControlApiV1ExtGrcControlsPostResponseCreateControlApiV1ExtGrcControlsPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateControlApiV1ExtGrcControlsPostBody,
) -> Response[
    CreateControlApiV1ExtGrcControlsPostResponseCreateControlApiV1ExtGrcControlsPost
    | HTTPValidationError
]:
    """Create Control

    Args:
        body (CreateControlApiV1ExtGrcControlsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateControlApiV1ExtGrcControlsPostResponseCreateControlApiV1ExtGrcControlsPost | HTTPValidationError]
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
    body: CreateControlApiV1ExtGrcControlsPostBody,
) -> (
    CreateControlApiV1ExtGrcControlsPostResponseCreateControlApiV1ExtGrcControlsPost
    | HTTPValidationError
    | None
):
    """Create Control

    Args:
        body (CreateControlApiV1ExtGrcControlsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateControlApiV1ExtGrcControlsPostResponseCreateControlApiV1ExtGrcControlsPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateControlApiV1ExtGrcControlsPostBody,
) -> Response[
    CreateControlApiV1ExtGrcControlsPostResponseCreateControlApiV1ExtGrcControlsPost
    | HTTPValidationError
]:
    """Create Control

    Args:
        body (CreateControlApiV1ExtGrcControlsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateControlApiV1ExtGrcControlsPostResponseCreateControlApiV1ExtGrcControlsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: CreateControlApiV1ExtGrcControlsPostBody,
) -> (
    CreateControlApiV1ExtGrcControlsPostResponseCreateControlApiV1ExtGrcControlsPost
    | HTTPValidationError
    | None
):
    """Create Control

    Args:
        body (CreateControlApiV1ExtGrcControlsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateControlApiV1ExtGrcControlsPostResponseCreateControlApiV1ExtGrcControlsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
