from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.step_up_api_v1_auth_step_up_post_body_type_0 import (
    StepUpApiV1AuthStepUpPostBodyType0,
)
from ...models.step_up_api_v1_auth_step_up_post_response_step_up_api_v1_auth_step_up_post import (
    StepUpApiV1AuthStepUpPostResponseStepUpApiV1AuthStepUpPost,
)
from ...types import UNSET, Unset
from typing import cast


def _get_kwargs(
    *,
    body: None | StepUpApiV1AuthStepUpPostBodyType0 | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/auth/step-up",
    }

    if isinstance(body, StepUpApiV1AuthStepUpPostBodyType0):
        _kwargs["json"] = body.to_dict()
    else:
        _kwargs["json"] = body

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | StepUpApiV1AuthStepUpPostResponseStepUpApiV1AuthStepUpPost | None:
    if response.status_code == 200:
        response_200 = StepUpApiV1AuthStepUpPostResponseStepUpApiV1AuthStepUpPost.from_dict(
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
) -> Response[HTTPValidationError | StepUpApiV1AuthStepUpPostResponseStepUpApiV1AuthStepUpPost]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: None | StepUpApiV1AuthStepUpPostBodyType0 | Unset = UNSET,
) -> Response[HTTPValidationError | StepUpApiV1AuthStepUpPostResponseStepUpApiV1AuthStepUpPost]:
    """Step Up

    Args:
        body (None | StepUpApiV1AuthStepUpPostBodyType0 | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | StepUpApiV1AuthStepUpPostResponseStepUpApiV1AuthStepUpPost]
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
    body: None | StepUpApiV1AuthStepUpPostBodyType0 | Unset = UNSET,
) -> HTTPValidationError | StepUpApiV1AuthStepUpPostResponseStepUpApiV1AuthStepUpPost | None:
    """Step Up

    Args:
        body (None | StepUpApiV1AuthStepUpPostBodyType0 | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | StepUpApiV1AuthStepUpPostResponseStepUpApiV1AuthStepUpPost
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: None | StepUpApiV1AuthStepUpPostBodyType0 | Unset = UNSET,
) -> Response[HTTPValidationError | StepUpApiV1AuthStepUpPostResponseStepUpApiV1AuthStepUpPost]:
    """Step Up

    Args:
        body (None | StepUpApiV1AuthStepUpPostBodyType0 | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | StepUpApiV1AuthStepUpPostResponseStepUpApiV1AuthStepUpPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: None | StepUpApiV1AuthStepUpPostBodyType0 | Unset = UNSET,
) -> HTTPValidationError | StepUpApiV1AuthStepUpPostResponseStepUpApiV1AuthStepUpPost | None:
    """Step Up

    Args:
        body (None | StepUpApiV1AuthStepUpPostBodyType0 | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | StepUpApiV1AuthStepUpPostResponseStepUpApiV1AuthStepUpPost
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
