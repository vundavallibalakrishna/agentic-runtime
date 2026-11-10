from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_push_subscription_api_v1_notifications_push_subscriptions_subscription_id_delete_response_delete_push_subscription_api_v1_notifications_push_subscriptions_subscription_id_delete import (
    DeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDeleteResponseDeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    subscription_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/notifications/push-subscriptions/{subscription_id}".format(
            subscription_id=quote(str(subscription_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDeleteResponseDeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDeleteResponseDeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDelete.from_dict(
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
    DeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDeleteResponseDeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDelete
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    subscription_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDeleteResponseDeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDelete
    | HTTPValidationError
]:
    """Delete Push Subscription

    Args:
        subscription_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDeleteResponseDeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        subscription_id=subscription_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    subscription_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDeleteResponseDeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDelete
    | HTTPValidationError
    | None
):
    """Delete Push Subscription

    Args:
        subscription_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDeleteResponseDeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDelete | HTTPValidationError
    """

    return sync_detailed(
        subscription_id=subscription_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    subscription_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDeleteResponseDeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDelete
    | HTTPValidationError
]:
    """Delete Push Subscription

    Args:
        subscription_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDeleteResponseDeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        subscription_id=subscription_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    subscription_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDeleteResponseDeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDelete
    | HTTPValidationError
    | None
):
    """Delete Push Subscription

    Args:
        subscription_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDeleteResponseDeletePushSubscriptionApiV1NotificationsPushSubscriptionsSubscriptionIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            subscription_id=subscription_id,
            client=client,
        )
    ).parsed
