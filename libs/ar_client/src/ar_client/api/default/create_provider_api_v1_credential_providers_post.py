from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_provider_api_v1_credential_providers_post_response_create_provider_api_v1_credential_providers_post import (
    CreateProviderApiV1CredentialProvidersPostResponseCreateProviderApiV1CredentialProvidersPost,
)
from ...models.credential_provider_body import CredentialProviderBody
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    *,
    body: CredentialProviderBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/credential-providers",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateProviderApiV1CredentialProvidersPostResponseCreateProviderApiV1CredentialProvidersPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CreateProviderApiV1CredentialProvidersPostResponseCreateProviderApiV1CredentialProvidersPost.from_dict(
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
    CreateProviderApiV1CredentialProvidersPostResponseCreateProviderApiV1CredentialProvidersPost
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
    body: CredentialProviderBody,
) -> Response[
    CreateProviderApiV1CredentialProvidersPostResponseCreateProviderApiV1CredentialProvidersPost
    | HTTPValidationError
]:
    """Create Provider

    Args:
        body (CredentialProviderBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateProviderApiV1CredentialProvidersPostResponseCreateProviderApiV1CredentialProvidersPost | HTTPValidationError]
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
    body: CredentialProviderBody,
) -> (
    CreateProviderApiV1CredentialProvidersPostResponseCreateProviderApiV1CredentialProvidersPost
    | HTTPValidationError
    | None
):
    """Create Provider

    Args:
        body (CredentialProviderBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateProviderApiV1CredentialProvidersPostResponseCreateProviderApiV1CredentialProvidersPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CredentialProviderBody,
) -> Response[
    CreateProviderApiV1CredentialProvidersPostResponseCreateProviderApiV1CredentialProvidersPost
    | HTTPValidationError
]:
    """Create Provider

    Args:
        body (CredentialProviderBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateProviderApiV1CredentialProvidersPostResponseCreateProviderApiV1CredentialProvidersPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: CredentialProviderBody,
) -> (
    CreateProviderApiV1CredentialProvidersPostResponseCreateProviderApiV1CredentialProvidersPost
    | HTTPValidationError
    | None
):
    """Create Provider

    Args:
        body (CredentialProviderBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateProviderApiV1CredentialProvidersPostResponseCreateProviderApiV1CredentialProvidersPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
