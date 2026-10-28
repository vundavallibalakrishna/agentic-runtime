from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_guest_api_v1_guests_guest_id_get_response_get_guest_api_v1_guests_guest_id_get import (
    GetGuestApiV1GuestsGuestIdGetResponseGetGuestApiV1GuestsGuestIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    guest_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/guests/{guest_id}".format(
            guest_id=quote(str(guest_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetGuestApiV1GuestsGuestIdGetResponseGetGuestApiV1GuestsGuestIdGet | HTTPValidationError | None
):
    if response.status_code == 200:
        response_200 = GetGuestApiV1GuestsGuestIdGetResponseGetGuestApiV1GuestsGuestIdGet.from_dict(
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
    GetGuestApiV1GuestsGuestIdGetResponseGetGuestApiV1GuestsGuestIdGet | HTTPValidationError
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
    GetGuestApiV1GuestsGuestIdGetResponseGetGuestApiV1GuestsGuestIdGet | HTTPValidationError
]:
    """Get Guest

    Args:
        guest_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetGuestApiV1GuestsGuestIdGetResponseGetGuestApiV1GuestsGuestIdGet | HTTPValidationError]
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
    GetGuestApiV1GuestsGuestIdGetResponseGetGuestApiV1GuestsGuestIdGet | HTTPValidationError | None
):
    """Get Guest

    Args:
        guest_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetGuestApiV1GuestsGuestIdGetResponseGetGuestApiV1GuestsGuestIdGet | HTTPValidationError
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
    GetGuestApiV1GuestsGuestIdGetResponseGetGuestApiV1GuestsGuestIdGet | HTTPValidationError
]:
    """Get Guest

    Args:
        guest_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetGuestApiV1GuestsGuestIdGetResponseGetGuestApiV1GuestsGuestIdGet | HTTPValidationError]
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
    GetGuestApiV1GuestsGuestIdGetResponseGetGuestApiV1GuestsGuestIdGet | HTTPValidationError | None
):
    """Get Guest

    Args:
        guest_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetGuestApiV1GuestsGuestIdGetResponseGetGuestApiV1GuestsGuestIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            guest_id=guest_id,
            client=client,
        )
    ).parsed
