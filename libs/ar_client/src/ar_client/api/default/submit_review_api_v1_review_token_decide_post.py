from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.review_decision import ReviewDecision
from ...models.submit_review_api_v1_review_token_decide_post_response_submit_review_api_v1_review_token_decide_post import (
    SubmitReviewApiV1ReviewTokenDecidePostResponseSubmitReviewApiV1ReviewTokenDecidePost,
)
from typing import cast


def _get_kwargs(
    token: str,
    *,
    body: ReviewDecision,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/review/{token}:decide".format(
            token=quote(str(token), safe=""),
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
    | SubmitReviewApiV1ReviewTokenDecidePostResponseSubmitReviewApiV1ReviewTokenDecidePost
    | None
):
    if response.status_code == 200:
        response_200 = SubmitReviewApiV1ReviewTokenDecidePostResponseSubmitReviewApiV1ReviewTokenDecidePost.from_dict(
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
    | SubmitReviewApiV1ReviewTokenDecidePostResponseSubmitReviewApiV1ReviewTokenDecidePost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    token: str,
    *,
    client: AuthenticatedClient | Client,
    body: ReviewDecision,
) -> Response[
    HTTPValidationError
    | SubmitReviewApiV1ReviewTokenDecidePostResponseSubmitReviewApiV1ReviewTokenDecidePost
]:
    """Submit Review

     Approve, reject, or approve with edited arguments.

    Args:
        token (str):
        body (ReviewDecision):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SubmitReviewApiV1ReviewTokenDecidePostResponseSubmitReviewApiV1ReviewTokenDecidePost]
    """

    kwargs = _get_kwargs(
        token=token,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    token: str,
    *,
    client: AuthenticatedClient | Client,
    body: ReviewDecision,
) -> (
    HTTPValidationError
    | SubmitReviewApiV1ReviewTokenDecidePostResponseSubmitReviewApiV1ReviewTokenDecidePost
    | None
):
    """Submit Review

     Approve, reject, or approve with edited arguments.

    Args:
        token (str):
        body (ReviewDecision):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SubmitReviewApiV1ReviewTokenDecidePostResponseSubmitReviewApiV1ReviewTokenDecidePost
    """

    return sync_detailed(
        token=token,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    token: str,
    *,
    client: AuthenticatedClient | Client,
    body: ReviewDecision,
) -> Response[
    HTTPValidationError
    | SubmitReviewApiV1ReviewTokenDecidePostResponseSubmitReviewApiV1ReviewTokenDecidePost
]:
    """Submit Review

     Approve, reject, or approve with edited arguments.

    Args:
        token (str):
        body (ReviewDecision):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SubmitReviewApiV1ReviewTokenDecidePostResponseSubmitReviewApiV1ReviewTokenDecidePost]
    """

    kwargs = _get_kwargs(
        token=token,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    token: str,
    *,
    client: AuthenticatedClient | Client,
    body: ReviewDecision,
) -> (
    HTTPValidationError
    | SubmitReviewApiV1ReviewTokenDecidePostResponseSubmitReviewApiV1ReviewTokenDecidePost
    | None
):
    """Submit Review

     Approve, reject, or approve with edited arguments.

    Args:
        token (str):
        body (ReviewDecision):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SubmitReviewApiV1ReviewTokenDecidePostResponseSubmitReviewApiV1ReviewTokenDecidePost
    """

    return (
        await asyncio_detailed(
            token=token,
            client=client,
            body=body,
        )
    ).parsed
