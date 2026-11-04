from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_resilience_api_v1_ext_grc_resilience_tests_post_body import (
    CreateResilienceApiV1ExtGrcResilienceTestsPostBody,
)
from ...models.create_resilience_api_v1_ext_grc_resilience_tests_post_response_create_resilience_api_v1_ext_grc_resilience_tests_post import (
    CreateResilienceApiV1ExtGrcResilienceTestsPostResponseCreateResilienceApiV1ExtGrcResilienceTestsPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    *,
    body: CreateResilienceApiV1ExtGrcResilienceTestsPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/resilience-tests",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateResilienceApiV1ExtGrcResilienceTestsPostResponseCreateResilienceApiV1ExtGrcResilienceTestsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CreateResilienceApiV1ExtGrcResilienceTestsPostResponseCreateResilienceApiV1ExtGrcResilienceTestsPost.from_dict(
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
    CreateResilienceApiV1ExtGrcResilienceTestsPostResponseCreateResilienceApiV1ExtGrcResilienceTestsPost
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
    body: CreateResilienceApiV1ExtGrcResilienceTestsPostBody,
) -> Response[
    CreateResilienceApiV1ExtGrcResilienceTestsPostResponseCreateResilienceApiV1ExtGrcResilienceTestsPost
    | HTTPValidationError
]:
    """Create Resilience

    Args:
        body (CreateResilienceApiV1ExtGrcResilienceTestsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateResilienceApiV1ExtGrcResilienceTestsPostResponseCreateResilienceApiV1ExtGrcResilienceTestsPost | HTTPValidationError]
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
    body: CreateResilienceApiV1ExtGrcResilienceTestsPostBody,
) -> (
    CreateResilienceApiV1ExtGrcResilienceTestsPostResponseCreateResilienceApiV1ExtGrcResilienceTestsPost
    | HTTPValidationError
    | None
):
    """Create Resilience

    Args:
        body (CreateResilienceApiV1ExtGrcResilienceTestsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateResilienceApiV1ExtGrcResilienceTestsPostResponseCreateResilienceApiV1ExtGrcResilienceTestsPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateResilienceApiV1ExtGrcResilienceTestsPostBody,
) -> Response[
    CreateResilienceApiV1ExtGrcResilienceTestsPostResponseCreateResilienceApiV1ExtGrcResilienceTestsPost
    | HTTPValidationError
]:
    """Create Resilience

    Args:
        body (CreateResilienceApiV1ExtGrcResilienceTestsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateResilienceApiV1ExtGrcResilienceTestsPostResponseCreateResilienceApiV1ExtGrcResilienceTestsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: CreateResilienceApiV1ExtGrcResilienceTestsPostBody,
) -> (
    CreateResilienceApiV1ExtGrcResilienceTestsPostResponseCreateResilienceApiV1ExtGrcResilienceTestsPost
    | HTTPValidationError
    | None
):
    """Create Resilience

    Args:
        body (CreateResilienceApiV1ExtGrcResilienceTestsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateResilienceApiV1ExtGrcResilienceTestsPostResponseCreateResilienceApiV1ExtGrcResilienceTestsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
