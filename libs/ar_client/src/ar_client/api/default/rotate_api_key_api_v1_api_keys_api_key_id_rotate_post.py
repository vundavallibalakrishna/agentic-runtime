from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.rotate_api_key_api_v1_api_keys_api_key_id_rotate_post_response_rotate_api_key_api_v1_api_keys_api_key_id_rotate_post import (
    RotateApiKeyApiV1ApiKeysApiKeyIdRotatePostResponseRotateApiKeyApiV1ApiKeysApiKeyIdRotatePost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    api_key_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/api-keys/{api_key_id}:rotate".format(
            api_key_id=quote(str(api_key_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | RotateApiKeyApiV1ApiKeysApiKeyIdRotatePostResponseRotateApiKeyApiV1ApiKeysApiKeyIdRotatePost
    | None
):
    if response.status_code == 200:
        response_200 = RotateApiKeyApiV1ApiKeysApiKeyIdRotatePostResponseRotateApiKeyApiV1ApiKeysApiKeyIdRotatePost.from_dict(
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
    | RotateApiKeyApiV1ApiKeysApiKeyIdRotatePostResponseRotateApiKeyApiV1ApiKeysApiKeyIdRotatePost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    api_key_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RotateApiKeyApiV1ApiKeysApiKeyIdRotatePostResponseRotateApiKeyApiV1ApiKeysApiKeyIdRotatePost
]:
    """Rotate Api Key

     Issue a new secret for the key, keeping its id. The new secret is shown once.

    Args:
        api_key_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RotateApiKeyApiV1ApiKeysApiKeyIdRotatePostResponseRotateApiKeyApiV1ApiKeysApiKeyIdRotatePost]
    """

    kwargs = _get_kwargs(
        api_key_id=api_key_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    api_key_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RotateApiKeyApiV1ApiKeysApiKeyIdRotatePostResponseRotateApiKeyApiV1ApiKeysApiKeyIdRotatePost
    | None
):
    """Rotate Api Key

     Issue a new secret for the key, keeping its id. The new secret is shown once.

    Args:
        api_key_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RotateApiKeyApiV1ApiKeysApiKeyIdRotatePostResponseRotateApiKeyApiV1ApiKeysApiKeyIdRotatePost
    """

    return sync_detailed(
        api_key_id=api_key_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    api_key_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RotateApiKeyApiV1ApiKeysApiKeyIdRotatePostResponseRotateApiKeyApiV1ApiKeysApiKeyIdRotatePost
]:
    """Rotate Api Key

     Issue a new secret for the key, keeping its id. The new secret is shown once.

    Args:
        api_key_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RotateApiKeyApiV1ApiKeysApiKeyIdRotatePostResponseRotateApiKeyApiV1ApiKeysApiKeyIdRotatePost]
    """

    kwargs = _get_kwargs(
        api_key_id=api_key_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    api_key_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RotateApiKeyApiV1ApiKeysApiKeyIdRotatePostResponseRotateApiKeyApiV1ApiKeysApiKeyIdRotatePost
    | None
):
    """Rotate Api Key

     Issue a new secret for the key, keeping its id. The new secret is shown once.

    Args:
        api_key_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RotateApiKeyApiV1ApiKeysApiKeyIdRotatePostResponseRotateApiKeyApiV1ApiKeysApiKeyIdRotatePost
    """

    return (
        await asyncio_detailed(
            api_key_id=api_key_id,
            client=client,
        )
    ).parsed
