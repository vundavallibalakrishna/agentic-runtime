from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.signup_api_v1_signup_post_response_signup_api_v1_signup_post import (
    SignupApiV1SignupPostResponseSignupApiV1SignupPost,
)
from ...models.signup_body import SignupBody
from typing import cast


def _get_kwargs(
    *,
    body: SignupBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/signup",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | SignupApiV1SignupPostResponseSignupApiV1SignupPost | None:
    if response.status_code == 200:
        response_200 = SignupApiV1SignupPostResponseSignupApiV1SignupPost.from_dict(response.json())

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
) -> Response[HTTPValidationError | SignupApiV1SignupPostResponseSignupApiV1SignupPost]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: SignupBody,
) -> Response[HTTPValidationError | SignupApiV1SignupPostResponseSignupApiV1SignupPost]:
    """Signup

    Args:
        body (SignupBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SignupApiV1SignupPostResponseSignupApiV1SignupPost]
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
    body: SignupBody,
) -> HTTPValidationError | SignupApiV1SignupPostResponseSignupApiV1SignupPost | None:
    """Signup

    Args:
        body (SignupBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SignupApiV1SignupPostResponseSignupApiV1SignupPost
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: SignupBody,
) -> Response[HTTPValidationError | SignupApiV1SignupPostResponseSignupApiV1SignupPost]:
    """Signup

    Args:
        body (SignupBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SignupApiV1SignupPostResponseSignupApiV1SignupPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: SignupBody,
) -> HTTPValidationError | SignupApiV1SignupPostResponseSignupApiV1SignupPost | None:
    """Signup

    Args:
        body (SignupBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SignupApiV1SignupPostResponseSignupApiV1SignupPost
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
