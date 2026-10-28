from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.release_body import ReleaseBody
from ...models.release_hold_api_v1_legal_holds_hold_id_release_post_response_release_hold_api_v1_legal_holds_hold_id_release_post import (
    ReleaseHoldApiV1LegalHoldsHoldIdReleasePostResponseReleaseHoldApiV1LegalHoldsHoldIdReleasePost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    hold_id: UUID,
    *,
    body: ReleaseBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/legal-holds/{hold_id}:release".format(
            hold_id=quote(str(hold_id), safe=""),
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
    | ReleaseHoldApiV1LegalHoldsHoldIdReleasePostResponseReleaseHoldApiV1LegalHoldsHoldIdReleasePost
    | None
):
    if response.status_code == 200:
        response_200 = ReleaseHoldApiV1LegalHoldsHoldIdReleasePostResponseReleaseHoldApiV1LegalHoldsHoldIdReleasePost.from_dict(
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
    | ReleaseHoldApiV1LegalHoldsHoldIdReleasePostResponseReleaseHoldApiV1LegalHoldsHoldIdReleasePost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    hold_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReleaseBody,
) -> Response[
    HTTPValidationError
    | ReleaseHoldApiV1LegalHoldsHoldIdReleasePostResponseReleaseHoldApiV1LegalHoldsHoldIdReleasePost
]:
    """Release Hold

    Args:
        hold_id (UUID):
        body (ReleaseBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ReleaseHoldApiV1LegalHoldsHoldIdReleasePostResponseReleaseHoldApiV1LegalHoldsHoldIdReleasePost]
    """

    kwargs = _get_kwargs(
        hold_id=hold_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    hold_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReleaseBody,
) -> (
    HTTPValidationError
    | ReleaseHoldApiV1LegalHoldsHoldIdReleasePostResponseReleaseHoldApiV1LegalHoldsHoldIdReleasePost
    | None
):
    """Release Hold

    Args:
        hold_id (UUID):
        body (ReleaseBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ReleaseHoldApiV1LegalHoldsHoldIdReleasePostResponseReleaseHoldApiV1LegalHoldsHoldIdReleasePost
    """

    return sync_detailed(
        hold_id=hold_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    hold_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReleaseBody,
) -> Response[
    HTTPValidationError
    | ReleaseHoldApiV1LegalHoldsHoldIdReleasePostResponseReleaseHoldApiV1LegalHoldsHoldIdReleasePost
]:
    """Release Hold

    Args:
        hold_id (UUID):
        body (ReleaseBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ReleaseHoldApiV1LegalHoldsHoldIdReleasePostResponseReleaseHoldApiV1LegalHoldsHoldIdReleasePost]
    """

    kwargs = _get_kwargs(
        hold_id=hold_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    hold_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReleaseBody,
) -> (
    HTTPValidationError
    | ReleaseHoldApiV1LegalHoldsHoldIdReleasePostResponseReleaseHoldApiV1LegalHoldsHoldIdReleasePost
    | None
):
    """Release Hold

    Args:
        hold_id (UUID):
        body (ReleaseBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ReleaseHoldApiV1LegalHoldsHoldIdReleasePostResponseReleaseHoldApiV1LegalHoldsHoldIdReleasePost
    """

    return (
        await asyncio_detailed(
            hold_id=hold_id,
            client=client,
            body=body,
        )
    ).parsed
