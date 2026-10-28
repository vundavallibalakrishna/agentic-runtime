from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.enroll_totp_api_v1_auth_guest_totp_enroll_post_response_enroll_totp_api_v1_auth_guest_totp_enroll_post import (
    EnrollTotpApiV1AuthGuestTotpEnrollPostResponseEnrollTotpApiV1AuthGuestTotpEnrollPost,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/auth/guest/totp/enroll",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> EnrollTotpApiV1AuthGuestTotpEnrollPostResponseEnrollTotpApiV1AuthGuestTotpEnrollPost | None:
    if response.status_code == 200:
        response_200 = EnrollTotpApiV1AuthGuestTotpEnrollPostResponseEnrollTotpApiV1AuthGuestTotpEnrollPost.from_dict(
            response.json()
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[EnrollTotpApiV1AuthGuestTotpEnrollPostResponseEnrollTotpApiV1AuthGuestTotpEnrollPost]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[EnrollTotpApiV1AuthGuestTotpEnrollPostResponseEnrollTotpApiV1AuthGuestTotpEnrollPost]:
    """Enroll Totp

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[EnrollTotpApiV1AuthGuestTotpEnrollPostResponseEnrollTotpApiV1AuthGuestTotpEnrollPost]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> EnrollTotpApiV1AuthGuestTotpEnrollPostResponseEnrollTotpApiV1AuthGuestTotpEnrollPost | None:
    """Enroll Totp

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        EnrollTotpApiV1AuthGuestTotpEnrollPostResponseEnrollTotpApiV1AuthGuestTotpEnrollPost
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[EnrollTotpApiV1AuthGuestTotpEnrollPostResponseEnrollTotpApiV1AuthGuestTotpEnrollPost]:
    """Enroll Totp

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[EnrollTotpApiV1AuthGuestTotpEnrollPostResponseEnrollTotpApiV1AuthGuestTotpEnrollPost]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> EnrollTotpApiV1AuthGuestTotpEnrollPostResponseEnrollTotpApiV1AuthGuestTotpEnrollPost | None:
    """Enroll Totp

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        EnrollTotpApiV1AuthGuestTotpEnrollPostResponseEnrollTotpApiV1AuthGuestTotpEnrollPost
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
