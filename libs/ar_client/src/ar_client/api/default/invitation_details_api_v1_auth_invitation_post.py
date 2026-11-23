from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.invitation_details_api_v1_auth_invitation_post_body_type_0 import (
    InvitationDetailsApiV1AuthInvitationPostBodyType0,
)
from ...types import UNSET, Unset
from typing import cast


def _get_kwargs(
    *,
    body: InvitationDetailsApiV1AuthInvitationPostBodyType0 | None | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/auth/invitation",
    }

    if isinstance(body, InvitationDetailsApiV1AuthInvitationPostBodyType0):
        _kwargs["json"] = body.to_dict()
    else:
        _kwargs["json"] = body

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = response.json()
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
) -> Response[Any | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: InvitationDetailsApiV1AuthInvitationPostBodyType0 | None | Unset = UNSET,
) -> Response[Any | HTTPValidationError]:
    """Invitation Details

     What a mailed invitation is for, so the page can say who is joining what.

    Args:
        body (InvitationDetailsApiV1AuthInvitationPostBodyType0 | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
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
    body: InvitationDetailsApiV1AuthInvitationPostBodyType0 | None | Unset = UNSET,
) -> Any | HTTPValidationError | None:
    """Invitation Details

     What a mailed invitation is for, so the page can say who is joining what.

    Args:
        body (InvitationDetailsApiV1AuthInvitationPostBodyType0 | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: InvitationDetailsApiV1AuthInvitationPostBodyType0 | None | Unset = UNSET,
) -> Response[Any | HTTPValidationError]:
    """Invitation Details

     What a mailed invitation is for, so the page can say who is joining what.

    Args:
        body (InvitationDetailsApiV1AuthInvitationPostBodyType0 | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: InvitationDetailsApiV1AuthInvitationPostBodyType0 | None | Unset = UNSET,
) -> Any | HTTPValidationError | None:
    """Invitation Details

     What a mailed invitation is for, so the page can say who is joining what.

    Args:
        body (InvitationDetailsApiV1AuthInvitationPostBodyType0 | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
