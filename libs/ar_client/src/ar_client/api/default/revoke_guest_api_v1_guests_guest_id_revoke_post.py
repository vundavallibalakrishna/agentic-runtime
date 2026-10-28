from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.revoke_guest_api_v1_guests_guest_id_revoke_post_response_revoke_guest_api_v1_guests_guest_id_revoke_post import (
    RevokeGuestApiV1GuestsGuestIdRevokePostResponseRevokeGuestApiV1GuestsGuestIdRevokePost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    guest_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/guests/{guest_id}:revoke".format(
            guest_id=quote(str(guest_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | RevokeGuestApiV1GuestsGuestIdRevokePostResponseRevokeGuestApiV1GuestsGuestIdRevokePost
    | None
):
    if response.status_code == 200:
        response_200 = RevokeGuestApiV1GuestsGuestIdRevokePostResponseRevokeGuestApiV1GuestsGuestIdRevokePost.from_dict(
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
    | RevokeGuestApiV1GuestsGuestIdRevokePostResponseRevokeGuestApiV1GuestsGuestIdRevokePost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    guest_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RevokeGuestApiV1GuestsGuestIdRevokePostResponseRevokeGuestApiV1GuestsGuestIdRevokePost
]:
    """Revoke Guest

    Args:
        guest_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RevokeGuestApiV1GuestsGuestIdRevokePostResponseRevokeGuestApiV1GuestsGuestIdRevokePost]
    """

    kwargs = _get_kwargs(
        guest_id=guest_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    guest_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RevokeGuestApiV1GuestsGuestIdRevokePostResponseRevokeGuestApiV1GuestsGuestIdRevokePost
    | None
):
    """Revoke Guest

    Args:
        guest_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RevokeGuestApiV1GuestsGuestIdRevokePostResponseRevokeGuestApiV1GuestsGuestIdRevokePost
    """

    return sync_detailed(
        guest_id=guest_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    guest_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RevokeGuestApiV1GuestsGuestIdRevokePostResponseRevokeGuestApiV1GuestsGuestIdRevokePost
]:
    """Revoke Guest

    Args:
        guest_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RevokeGuestApiV1GuestsGuestIdRevokePostResponseRevokeGuestApiV1GuestsGuestIdRevokePost]
    """

    kwargs = _get_kwargs(
        guest_id=guest_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    guest_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RevokeGuestApiV1GuestsGuestIdRevokePostResponseRevokeGuestApiV1GuestsGuestIdRevokePost
    | None
):
    """Revoke Guest

    Args:
        guest_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RevokeGuestApiV1GuestsGuestIdRevokePostResponseRevokeGuestApiV1GuestsGuestIdRevokePost
    """

    return (
        await asyncio_detailed(
            guest_id=guest_id,
            client=client,
        )
    ).parsed
