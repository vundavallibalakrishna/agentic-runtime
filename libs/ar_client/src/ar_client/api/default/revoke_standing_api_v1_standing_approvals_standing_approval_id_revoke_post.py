from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.revoke_standing_api_v1_standing_approvals_standing_approval_id_revoke_post_response_revoke_standing_api_v1_standing_approvals_standing_approval_id_revoke_post import (
    RevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePostResponseRevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    standing_approval_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/standing-approvals/{standing_approval_id}:revoke".format(
            standing_approval_id=quote(str(standing_approval_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | RevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePostResponseRevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePost
    | None
):
    if response.status_code == 200:
        response_200 = RevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePostResponseRevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePost.from_dict(
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
    | RevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePostResponseRevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    standing_approval_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePostResponseRevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePost
]:
    """Revoke Standing

    Args:
        standing_approval_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePostResponseRevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePost]
    """

    kwargs = _get_kwargs(
        standing_approval_id=standing_approval_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    standing_approval_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePostResponseRevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePost
    | None
):
    """Revoke Standing

    Args:
        standing_approval_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePostResponseRevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePost
    """

    return sync_detailed(
        standing_approval_id=standing_approval_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    standing_approval_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePostResponseRevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePost
]:
    """Revoke Standing

    Args:
        standing_approval_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePostResponseRevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePost]
    """

    kwargs = _get_kwargs(
        standing_approval_id=standing_approval_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    standing_approval_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePostResponseRevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePost
    | None
):
    """Revoke Standing

    Args:
        standing_approval_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePostResponseRevokeStandingApiV1StandingApprovalsStandingApprovalIdRevokePost
    """

    return (
        await asyncio_detailed(
            standing_approval_id=standing_approval_id,
            client=client,
        )
    ).parsed
