from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.revoke_invitation_api_v1_invitations_invitation_id_delete_response_revoke_invitation_api_v1_invitations_invitation_id_delete import (
    RevokeInvitationApiV1InvitationsInvitationIdDeleteResponseRevokeInvitationApiV1InvitationsInvitationIdDelete,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    invitation_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/invitations/{invitation_id}".format(
            invitation_id=quote(str(invitation_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | RevokeInvitationApiV1InvitationsInvitationIdDeleteResponseRevokeInvitationApiV1InvitationsInvitationIdDelete
    | None
):
    if response.status_code == 200:
        response_200 = RevokeInvitationApiV1InvitationsInvitationIdDeleteResponseRevokeInvitationApiV1InvitationsInvitationIdDelete.from_dict(
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
    | RevokeInvitationApiV1InvitationsInvitationIdDeleteResponseRevokeInvitationApiV1InvitationsInvitationIdDelete
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    invitation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RevokeInvitationApiV1InvitationsInvitationIdDeleteResponseRevokeInvitationApiV1InvitationsInvitationIdDelete
]:
    """Revoke Invitation

    Args:
        invitation_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RevokeInvitationApiV1InvitationsInvitationIdDeleteResponseRevokeInvitationApiV1InvitationsInvitationIdDelete]
    """

    kwargs = _get_kwargs(
        invitation_id=invitation_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    invitation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RevokeInvitationApiV1InvitationsInvitationIdDeleteResponseRevokeInvitationApiV1InvitationsInvitationIdDelete
    | None
):
    """Revoke Invitation

    Args:
        invitation_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RevokeInvitationApiV1InvitationsInvitationIdDeleteResponseRevokeInvitationApiV1InvitationsInvitationIdDelete
    """

    return sync_detailed(
        invitation_id=invitation_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    invitation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RevokeInvitationApiV1InvitationsInvitationIdDeleteResponseRevokeInvitationApiV1InvitationsInvitationIdDelete
]:
    """Revoke Invitation

    Args:
        invitation_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RevokeInvitationApiV1InvitationsInvitationIdDeleteResponseRevokeInvitationApiV1InvitationsInvitationIdDelete]
    """

    kwargs = _get_kwargs(
        invitation_id=invitation_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    invitation_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RevokeInvitationApiV1InvitationsInvitationIdDeleteResponseRevokeInvitationApiV1InvitationsInvitationIdDelete
    | None
):
    """Revoke Invitation

    Args:
        invitation_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RevokeInvitationApiV1InvitationsInvitationIdDeleteResponseRevokeInvitationApiV1InvitationsInvitationIdDelete
    """

    return (
        await asyncio_detailed(
            invitation_id=invitation_id,
            client=client,
        )
    ).parsed
