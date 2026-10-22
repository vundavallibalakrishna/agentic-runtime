from http import HTTPStatus
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.session_message import SessionMessage
from ...models.session_message_api_v1_builder_sessions_session_id_messages_post_response_session_message_api_v1_builder_sessions_session_id_messages_post import (
    SessionMessageApiV1BuilderSessionsSessionIdMessagesPostResponseSessionMessageApiV1BuilderSessionsSessionIdMessagesPost,
)
from ...types import Response


def _get_kwargs(
    session_id: UUID,
    *,
    body: SessionMessage,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/builder/sessions/{session_id}/messages".format(
            session_id=quote(str(session_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | SessionMessageApiV1BuilderSessionsSessionIdMessagesPostResponseSessionMessageApiV1BuilderSessionsSessionIdMessagesPost
    | None
):
    if response.status_code == 200:
        response_200 = SessionMessageApiV1BuilderSessionsSessionIdMessagesPostResponseSessionMessageApiV1BuilderSessionsSessionIdMessagesPost.from_dict(
            response.json()
        )

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    HTTPValidationError
    | SessionMessageApiV1BuilderSessionsSessionIdMessagesPostResponseSessionMessageApiV1BuilderSessionsSessionIdMessagesPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    session_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SessionMessage,
) -> Response[
    HTTPValidationError
    | SessionMessageApiV1BuilderSessionsSessionIdMessagesPostResponseSessionMessageApiV1BuilderSessionsSessionIdMessagesPost
]:
    """Session Message

    Args:
        session_id (UUID):
        body (SessionMessage):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SessionMessageApiV1BuilderSessionsSessionIdMessagesPostResponseSessionMessageApiV1BuilderSessionsSessionIdMessagesPost]
    """

    kwargs = _get_kwargs(
        session_id=session_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    session_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SessionMessage,
) -> (
    HTTPValidationError
    | SessionMessageApiV1BuilderSessionsSessionIdMessagesPostResponseSessionMessageApiV1BuilderSessionsSessionIdMessagesPost
    | None
):
    """Session Message

    Args:
        session_id (UUID):
        body (SessionMessage):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SessionMessageApiV1BuilderSessionsSessionIdMessagesPostResponseSessionMessageApiV1BuilderSessionsSessionIdMessagesPost
    """

    return sync_detailed(
        session_id=session_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    session_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SessionMessage,
) -> Response[
    HTTPValidationError
    | SessionMessageApiV1BuilderSessionsSessionIdMessagesPostResponseSessionMessageApiV1BuilderSessionsSessionIdMessagesPost
]:
    """Session Message

    Args:
        session_id (UUID):
        body (SessionMessage):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SessionMessageApiV1BuilderSessionsSessionIdMessagesPostResponseSessionMessageApiV1BuilderSessionsSessionIdMessagesPost]
    """

    kwargs = _get_kwargs(
        session_id=session_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    session_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SessionMessage,
) -> (
    HTTPValidationError
    | SessionMessageApiV1BuilderSessionsSessionIdMessagesPostResponseSessionMessageApiV1BuilderSessionsSessionIdMessagesPost
    | None
):
    """Session Message

    Args:
        session_id (UUID):
        body (SessionMessage):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SessionMessageApiV1BuilderSessionsSessionIdMessagesPostResponseSessionMessageApiV1BuilderSessionsSessionIdMessagesPost
    """

    return (
        await asyncio_detailed(
            session_id=session_id,
            client=client,
            body=body,
        )
    ).parsed
