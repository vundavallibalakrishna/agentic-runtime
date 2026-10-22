from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.decide_item_api_v1_review_items_review_item_id_decide_post_response_decide_item_api_v1_review_items_review_item_id_decide_post import (
    DecideItemApiV1ReviewItemsReviewItemIdDecidePostResponseDecideItemApiV1ReviewItemsReviewItemIdDecidePost,
)
from ...models.http_validation_error import HTTPValidationError
from ...models.review_decide_body import ReviewDecideBody
from typing import cast
from uuid import UUID


def _get_kwargs(
    review_item_id: UUID,
    *,
    body: ReviewDecideBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/review-items/{review_item_id}:decide".format(
            review_item_id=quote(str(review_item_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DecideItemApiV1ReviewItemsReviewItemIdDecidePostResponseDecideItemApiV1ReviewItemsReviewItemIdDecidePost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DecideItemApiV1ReviewItemsReviewItemIdDecidePostResponseDecideItemApiV1ReviewItemsReviewItemIdDecidePost.from_dict(
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
    DecideItemApiV1ReviewItemsReviewItemIdDecidePostResponseDecideItemApiV1ReviewItemsReviewItemIdDecidePost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    review_item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReviewDecideBody,
) -> Response[
    DecideItemApiV1ReviewItemsReviewItemIdDecidePostResponseDecideItemApiV1ReviewItemsReviewItemIdDecidePost
    | HTTPValidationError
]:
    """Decide Item

    Args:
        review_item_id (UUID):
        body (ReviewDecideBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DecideItemApiV1ReviewItemsReviewItemIdDecidePostResponseDecideItemApiV1ReviewItemsReviewItemIdDecidePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        review_item_id=review_item_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    review_item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReviewDecideBody,
) -> (
    DecideItemApiV1ReviewItemsReviewItemIdDecidePostResponseDecideItemApiV1ReviewItemsReviewItemIdDecidePost
    | HTTPValidationError
    | None
):
    """Decide Item

    Args:
        review_item_id (UUID):
        body (ReviewDecideBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DecideItemApiV1ReviewItemsReviewItemIdDecidePostResponseDecideItemApiV1ReviewItemsReviewItemIdDecidePost | HTTPValidationError
    """

    return sync_detailed(
        review_item_id=review_item_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    review_item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReviewDecideBody,
) -> Response[
    DecideItemApiV1ReviewItemsReviewItemIdDecidePostResponseDecideItemApiV1ReviewItemsReviewItemIdDecidePost
    | HTTPValidationError
]:
    """Decide Item

    Args:
        review_item_id (UUID):
        body (ReviewDecideBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DecideItemApiV1ReviewItemsReviewItemIdDecidePostResponseDecideItemApiV1ReviewItemsReviewItemIdDecidePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        review_item_id=review_item_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    review_item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ReviewDecideBody,
) -> (
    DecideItemApiV1ReviewItemsReviewItemIdDecidePostResponseDecideItemApiV1ReviewItemsReviewItemIdDecidePost
    | HTTPValidationError
    | None
):
    """Decide Item

    Args:
        review_item_id (UUID):
        body (ReviewDecideBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DecideItemApiV1ReviewItemsReviewItemIdDecidePostResponseDecideItemApiV1ReviewItemsReviewItemIdDecidePost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            review_item_id=review_item_id,
            client=client,
            body=body,
        )
    ).parsed
