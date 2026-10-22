from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.mark_read_api_v1_notifications_notification_id_read_post_response_mark_read_api_v1_notifications_notification_id_read_post import (
    MarkReadApiV1NotificationsNotificationIdReadPostResponseMarkReadApiV1NotificationsNotificationIdReadPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    notification_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/notifications/{notification_id}:read".format(
            notification_id=quote(str(notification_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | MarkReadApiV1NotificationsNotificationIdReadPostResponseMarkReadApiV1NotificationsNotificationIdReadPost
    | None
):
    if response.status_code == 200:
        response_200 = MarkReadApiV1NotificationsNotificationIdReadPostResponseMarkReadApiV1NotificationsNotificationIdReadPost.from_dict(
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
    | MarkReadApiV1NotificationsNotificationIdReadPostResponseMarkReadApiV1NotificationsNotificationIdReadPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    notification_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | MarkReadApiV1NotificationsNotificationIdReadPostResponseMarkReadApiV1NotificationsNotificationIdReadPost
]:
    """Mark Read

    Args:
        notification_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | MarkReadApiV1NotificationsNotificationIdReadPostResponseMarkReadApiV1NotificationsNotificationIdReadPost]
    """

    kwargs = _get_kwargs(
        notification_id=notification_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    notification_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | MarkReadApiV1NotificationsNotificationIdReadPostResponseMarkReadApiV1NotificationsNotificationIdReadPost
    | None
):
    """Mark Read

    Args:
        notification_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | MarkReadApiV1NotificationsNotificationIdReadPostResponseMarkReadApiV1NotificationsNotificationIdReadPost
    """

    return sync_detailed(
        notification_id=notification_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    notification_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | MarkReadApiV1NotificationsNotificationIdReadPostResponseMarkReadApiV1NotificationsNotificationIdReadPost
]:
    """Mark Read

    Args:
        notification_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | MarkReadApiV1NotificationsNotificationIdReadPostResponseMarkReadApiV1NotificationsNotificationIdReadPost]
    """

    kwargs = _get_kwargs(
        notification_id=notification_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    notification_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | MarkReadApiV1NotificationsNotificationIdReadPostResponseMarkReadApiV1NotificationsNotificationIdReadPost
    | None
):
    """Mark Read

    Args:
        notification_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | MarkReadApiV1NotificationsNotificationIdReadPostResponseMarkReadApiV1NotificationsNotificationIdReadPost
    """

    return (
        await asyncio_detailed(
            notification_id=notification_id,
            client=client,
        )
    ).parsed
