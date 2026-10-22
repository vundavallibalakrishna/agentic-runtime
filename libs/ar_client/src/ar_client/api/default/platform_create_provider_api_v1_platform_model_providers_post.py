from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.platform_create_provider_api_v1_platform_model_providers_post_response_platform_create_provider_api_v1_platform_model_providers_post import (
    PlatformCreateProviderApiV1PlatformModelProvidersPostResponsePlatformCreateProviderApiV1PlatformModelProvidersPost,
)
from ...models.provider_body import ProviderBody
from typing import cast


def _get_kwargs(
    *,
    body: ProviderBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/platform/model-providers",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | PlatformCreateProviderApiV1PlatformModelProvidersPostResponsePlatformCreateProviderApiV1PlatformModelProvidersPost
    | None
):
    if response.status_code == 200:
        response_200 = PlatformCreateProviderApiV1PlatformModelProvidersPostResponsePlatformCreateProviderApiV1PlatformModelProvidersPost.from_dict(
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
    HTTPValidationError
    | PlatformCreateProviderApiV1PlatformModelProvidersPostResponsePlatformCreateProviderApiV1PlatformModelProvidersPost
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
    body: ProviderBody,
) -> Response[
    HTTPValidationError
    | PlatformCreateProviderApiV1PlatformModelProvidersPostResponsePlatformCreateProviderApiV1PlatformModelProvidersPost
]:
    """Platform Create Provider

    Args:
        body (ProviderBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PlatformCreateProviderApiV1PlatformModelProvidersPostResponsePlatformCreateProviderApiV1PlatformModelProvidersPost]
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
    body: ProviderBody,
) -> (
    HTTPValidationError
    | PlatformCreateProviderApiV1PlatformModelProvidersPostResponsePlatformCreateProviderApiV1PlatformModelProvidersPost
    | None
):
    """Platform Create Provider

    Args:
        body (ProviderBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PlatformCreateProviderApiV1PlatformModelProvidersPostResponsePlatformCreateProviderApiV1PlatformModelProvidersPost
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ProviderBody,
) -> Response[
    HTTPValidationError
    | PlatformCreateProviderApiV1PlatformModelProvidersPostResponsePlatformCreateProviderApiV1PlatformModelProvidersPost
]:
    """Platform Create Provider

    Args:
        body (ProviderBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PlatformCreateProviderApiV1PlatformModelProvidersPostResponsePlatformCreateProviderApiV1PlatformModelProvidersPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: ProviderBody,
) -> (
    HTTPValidationError
    | PlatformCreateProviderApiV1PlatformModelProvidersPostResponsePlatformCreateProviderApiV1PlatformModelProvidersPost
    | None
):
    """Platform Create Provider

    Args:
        body (ProviderBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PlatformCreateProviderApiV1PlatformModelProvidersPostResponsePlatformCreateProviderApiV1PlatformModelProvidersPost
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
