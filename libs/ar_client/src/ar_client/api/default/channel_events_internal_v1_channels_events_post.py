from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.channel_event_body import ChannelEventBody
from ...models.channel_events_internal_v1_channels_events_post_response_channel_events_internal_v1_channels_events_post import (
    ChannelEventsInternalV1ChannelsEventsPostResponseChannelEventsInternalV1ChannelsEventsPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    *,
    body: ChannelEventBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/internal/v1/channels/events",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ChannelEventsInternalV1ChannelsEventsPostResponseChannelEventsInternalV1ChannelsEventsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = ChannelEventsInternalV1ChannelsEventsPostResponseChannelEventsInternalV1ChannelsEventsPost.from_dict(
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
    ChannelEventsInternalV1ChannelsEventsPostResponseChannelEventsInternalV1ChannelsEventsPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ChannelEventBody,
) -> Response[
    ChannelEventsInternalV1ChannelsEventsPostResponseChannelEventsInternalV1ChannelsEventsPost
    | HTTPValidationError
]:
    """Channel Events

    Args:
        body (ChannelEventBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ChannelEventsInternalV1ChannelsEventsPostResponseChannelEventsInternalV1ChannelsEventsPost | HTTPValidationError]
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
    body: ChannelEventBody,
) -> (
    ChannelEventsInternalV1ChannelsEventsPostResponseChannelEventsInternalV1ChannelsEventsPost
    | HTTPValidationError
    | None
):
    """Channel Events

    Args:
        body (ChannelEventBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ChannelEventsInternalV1ChannelsEventsPostResponseChannelEventsInternalV1ChannelsEventsPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ChannelEventBody,
) -> Response[
    ChannelEventsInternalV1ChannelsEventsPostResponseChannelEventsInternalV1ChannelsEventsPost
    | HTTPValidationError
]:
    """Channel Events

    Args:
        body (ChannelEventBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ChannelEventsInternalV1ChannelsEventsPostResponseChannelEventsInternalV1ChannelsEventsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: ChannelEventBody,
) -> (
    ChannelEventsInternalV1ChannelsEventsPostResponseChannelEventsInternalV1ChannelsEventsPost
    | HTTPValidationError
    | None
):
    """Channel Events

    Args:
        body (ChannelEventBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ChannelEventsInternalV1ChannelsEventsPostResponseChannelEventsInternalV1ChannelsEventsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
