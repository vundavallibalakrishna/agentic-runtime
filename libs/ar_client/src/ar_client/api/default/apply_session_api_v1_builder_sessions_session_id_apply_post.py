from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.apply_body import ApplyBody
from ...models.apply_session_api_v1_builder_sessions_session_id_apply_post_response_apply_session_api_v1_builder_sessions_session_id_apply_post import (
    ApplySessionApiV1BuilderSessionsSessionIdApplyPostResponseApplySessionApiV1BuilderSessionsSessionIdApplyPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    session_id: UUID,
    *,
    body: ApplyBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/builder/sessions/{session_id}:apply".format(
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
    ApplySessionApiV1BuilderSessionsSessionIdApplyPostResponseApplySessionApiV1BuilderSessionsSessionIdApplyPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = ApplySessionApiV1BuilderSessionsSessionIdApplyPostResponseApplySessionApiV1BuilderSessionsSessionIdApplyPost.from_dict(
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
    ApplySessionApiV1BuilderSessionsSessionIdApplyPostResponseApplySessionApiV1BuilderSessionsSessionIdApplyPost
    | HTTPValidationError
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
    body: ApplyBody,
) -> Response[
    ApplySessionApiV1BuilderSessionsSessionIdApplyPostResponseApplySessionApiV1BuilderSessionsSessionIdApplyPost
    | HTTPValidationError
]:
    """Apply Session

    Args:
        session_id (UUID):
        body (ApplyBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApplySessionApiV1BuilderSessionsSessionIdApplyPostResponseApplySessionApiV1BuilderSessionsSessionIdApplyPost | HTTPValidationError]
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
    body: ApplyBody,
) -> (
    ApplySessionApiV1BuilderSessionsSessionIdApplyPostResponseApplySessionApiV1BuilderSessionsSessionIdApplyPost
    | HTTPValidationError
    | None
):
    """Apply Session

    Args:
        session_id (UUID):
        body (ApplyBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApplySessionApiV1BuilderSessionsSessionIdApplyPostResponseApplySessionApiV1BuilderSessionsSessionIdApplyPost | HTTPValidationError
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
    body: ApplyBody,
) -> Response[
    ApplySessionApiV1BuilderSessionsSessionIdApplyPostResponseApplySessionApiV1BuilderSessionsSessionIdApplyPost
    | HTTPValidationError
]:
    """Apply Session

    Args:
        session_id (UUID):
        body (ApplyBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApplySessionApiV1BuilderSessionsSessionIdApplyPostResponseApplySessionApiV1BuilderSessionsSessionIdApplyPost | HTTPValidationError]
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
    body: ApplyBody,
) -> (
    ApplySessionApiV1BuilderSessionsSessionIdApplyPostResponseApplySessionApiV1BuilderSessionsSessionIdApplyPost
    | HTTPValidationError
    | None
):
    """Apply Session

    Args:
        session_id (UUID):
        body (ApplyBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApplySessionApiV1BuilderSessionsSessionIdApplyPostResponseApplySessionApiV1BuilderSessionsSessionIdApplyPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            session_id=session_id,
            client=client,
            body=body,
        )
    ).parsed
