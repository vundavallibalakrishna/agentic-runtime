from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.accept_body import AcceptBody
from ...models.accept_message_api_v1_messages_message_id_accept_post_response_accept_message_api_v1_messages_message_id_accept_post import (
    AcceptMessageApiV1MessagesMessageIdAcceptPostResponseAcceptMessageApiV1MessagesMessageIdAcceptPost,
)
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    message_id: UUID,
    *,
    body: AcceptBody | None | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/messages/{message_id}:accept".format(
            message_id=quote(str(message_id), safe=""),
        ),
    }

    if isinstance(body, AcceptBody):
        _kwargs["json"] = body.to_dict()
    else:
        _kwargs["json"] = body

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    AcceptMessageApiV1MessagesMessageIdAcceptPostResponseAcceptMessageApiV1MessagesMessageIdAcceptPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = AcceptMessageApiV1MessagesMessageIdAcceptPostResponseAcceptMessageApiV1MessagesMessageIdAcceptPost.from_dict(
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
    AcceptMessageApiV1MessagesMessageIdAcceptPostResponseAcceptMessageApiV1MessagesMessageIdAcceptPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AcceptBody | None | Unset = UNSET,
) -> Response[
    AcceptMessageApiV1MessagesMessageIdAcceptPostResponseAcceptMessageApiV1MessagesMessageIdAcceptPost
    | HTTPValidationError
]:
    """Accept Message

     Record that the caller reviewed one assistant reply and accepts it as it reads now.

    Args:
        message_id (UUID):
        body (AcceptBody | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AcceptMessageApiV1MessagesMessageIdAcceptPostResponseAcceptMessageApiV1MessagesMessageIdAcceptPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        message_id=message_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AcceptBody | None | Unset = UNSET,
) -> (
    AcceptMessageApiV1MessagesMessageIdAcceptPostResponseAcceptMessageApiV1MessagesMessageIdAcceptPost
    | HTTPValidationError
    | None
):
    """Accept Message

     Record that the caller reviewed one assistant reply and accepts it as it reads now.

    Args:
        message_id (UUID):
        body (AcceptBody | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AcceptMessageApiV1MessagesMessageIdAcceptPostResponseAcceptMessageApiV1MessagesMessageIdAcceptPost | HTTPValidationError
    """

    return sync_detailed(
        message_id=message_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AcceptBody | None | Unset = UNSET,
) -> Response[
    AcceptMessageApiV1MessagesMessageIdAcceptPostResponseAcceptMessageApiV1MessagesMessageIdAcceptPost
    | HTTPValidationError
]:
    """Accept Message

     Record that the caller reviewed one assistant reply and accepts it as it reads now.

    Args:
        message_id (UUID):
        body (AcceptBody | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AcceptMessageApiV1MessagesMessageIdAcceptPostResponseAcceptMessageApiV1MessagesMessageIdAcceptPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        message_id=message_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AcceptBody | None | Unset = UNSET,
) -> (
    AcceptMessageApiV1MessagesMessageIdAcceptPostResponseAcceptMessageApiV1MessagesMessageIdAcceptPost
    | HTTPValidationError
    | None
):
    """Accept Message

     Record that the caller reviewed one assistant reply and accepts it as it reads now.

    Args:
        message_id (UUID):
        body (AcceptBody | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AcceptMessageApiV1MessagesMessageIdAcceptPostResponseAcceptMessageApiV1MessagesMessageIdAcceptPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            message_id=message_id,
            client=client,
            body=body,
        )
    ).parsed
