from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_grant_api_v1_guests_guest_id_grants_post_response_create_grant_api_v1_guests_guest_id_grants_post import (
    CreateGrantApiV1GuestsGuestIdGrantsPostResponseCreateGrantApiV1GuestsGuestIdGrantsPost,
)
from ...models.grant_body import GrantBody
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    guest_id: UUID,
    *,
    body: GrantBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/guests/{guest_id}/grants".format(
            guest_id=quote(str(guest_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateGrantApiV1GuestsGuestIdGrantsPostResponseCreateGrantApiV1GuestsGuestIdGrantsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CreateGrantApiV1GuestsGuestIdGrantsPostResponseCreateGrantApiV1GuestsGuestIdGrantsPost.from_dict(
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
    CreateGrantApiV1GuestsGuestIdGrantsPostResponseCreateGrantApiV1GuestsGuestIdGrantsPost
    | HTTPValidationError
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
    body: GrantBody,
) -> Response[
    CreateGrantApiV1GuestsGuestIdGrantsPostResponseCreateGrantApiV1GuestsGuestIdGrantsPost
    | HTTPValidationError
]:
    """Create Grant

    Args:
        guest_id (UUID):
        body (GrantBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateGrantApiV1GuestsGuestIdGrantsPostResponseCreateGrantApiV1GuestsGuestIdGrantsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        guest_id=guest_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    guest_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: GrantBody,
) -> (
    CreateGrantApiV1GuestsGuestIdGrantsPostResponseCreateGrantApiV1GuestsGuestIdGrantsPost
    | HTTPValidationError
    | None
):
    """Create Grant

    Args:
        guest_id (UUID):
        body (GrantBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateGrantApiV1GuestsGuestIdGrantsPostResponseCreateGrantApiV1GuestsGuestIdGrantsPost | HTTPValidationError
    """

    return sync_detailed(
        guest_id=guest_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    guest_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: GrantBody,
) -> Response[
    CreateGrantApiV1GuestsGuestIdGrantsPostResponseCreateGrantApiV1GuestsGuestIdGrantsPost
    | HTTPValidationError
]:
    """Create Grant

    Args:
        guest_id (UUID):
        body (GrantBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateGrantApiV1GuestsGuestIdGrantsPostResponseCreateGrantApiV1GuestsGuestIdGrantsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        guest_id=guest_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    guest_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: GrantBody,
) -> (
    CreateGrantApiV1GuestsGuestIdGrantsPostResponseCreateGrantApiV1GuestsGuestIdGrantsPost
    | HTTPValidationError
    | None
):
    """Create Grant

    Args:
        guest_id (UUID):
        body (GrantBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateGrantApiV1GuestsGuestIdGrantsPostResponseCreateGrantApiV1GuestsGuestIdGrantsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            guest_id=guest_id,
            client=client,
            body=body,
        )
    ).parsed
