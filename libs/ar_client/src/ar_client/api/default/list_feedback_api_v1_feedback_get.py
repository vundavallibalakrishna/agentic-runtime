from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_feedback_api_v1_feedback_get_response_list_feedback_api_v1_feedback_get import (
    ListFeedbackApiV1FeedbackGetResponseListFeedbackApiV1FeedbackGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/feedback",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ListFeedbackApiV1FeedbackGetResponseListFeedbackApiV1FeedbackGet | None:
    if response.status_code == 200:
        response_200 = ListFeedbackApiV1FeedbackGetResponseListFeedbackApiV1FeedbackGet.from_dict(
            response.json()
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ListFeedbackApiV1FeedbackGetResponseListFeedbackApiV1FeedbackGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListFeedbackApiV1FeedbackGetResponseListFeedbackApiV1FeedbackGet]:
    """List Feedback

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListFeedbackApiV1FeedbackGetResponseListFeedbackApiV1FeedbackGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> ListFeedbackApiV1FeedbackGetResponseListFeedbackApiV1FeedbackGet | None:
    """List Feedback

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListFeedbackApiV1FeedbackGetResponseListFeedbackApiV1FeedbackGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListFeedbackApiV1FeedbackGetResponseListFeedbackApiV1FeedbackGet]:
    """List Feedback

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListFeedbackApiV1FeedbackGetResponseListFeedbackApiV1FeedbackGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> ListFeedbackApiV1FeedbackGetResponseListFeedbackApiV1FeedbackGet | None:
    """List Feedback

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListFeedbackApiV1FeedbackGetResponseListFeedbackApiV1FeedbackGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
