from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_item_api_v1_review_items_review_item_id_get_response_get_item_api_v1_review_items_review_item_id_get import (
    GetItemApiV1ReviewItemsReviewItemIdGetResponseGetItemApiV1ReviewItemsReviewItemIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    review_item_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/review-items/{review_item_id}".format(
            review_item_id=quote(str(review_item_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetItemApiV1ReviewItemsReviewItemIdGetResponseGetItemApiV1ReviewItemsReviewItemIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetItemApiV1ReviewItemsReviewItemIdGetResponseGetItemApiV1ReviewItemsReviewItemIdGet.from_dict(
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
    GetItemApiV1ReviewItemsReviewItemIdGetResponseGetItemApiV1ReviewItemsReviewItemIdGet
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
) -> Response[
    GetItemApiV1ReviewItemsReviewItemIdGetResponseGetItemApiV1ReviewItemsReviewItemIdGet
    | HTTPValidationError
]:
    """Get Item

    Args:
        review_item_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetItemApiV1ReviewItemsReviewItemIdGetResponseGetItemApiV1ReviewItemsReviewItemIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        review_item_id=review_item_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    review_item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetItemApiV1ReviewItemsReviewItemIdGetResponseGetItemApiV1ReviewItemsReviewItemIdGet
    | HTTPValidationError
    | None
):
    """Get Item

    Args:
        review_item_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetItemApiV1ReviewItemsReviewItemIdGetResponseGetItemApiV1ReviewItemsReviewItemIdGet | HTTPValidationError
    """

    return sync_detailed(
        review_item_id=review_item_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    review_item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetItemApiV1ReviewItemsReviewItemIdGetResponseGetItemApiV1ReviewItemsReviewItemIdGet
    | HTTPValidationError
]:
    """Get Item

    Args:
        review_item_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetItemApiV1ReviewItemsReviewItemIdGetResponseGetItemApiV1ReviewItemsReviewItemIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        review_item_id=review_item_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    review_item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetItemApiV1ReviewItemsReviewItemIdGetResponseGetItemApiV1ReviewItemsReviewItemIdGet
    | HTTPValidationError
    | None
):
    """Get Item

    Args:
        review_item_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetItemApiV1ReviewItemsReviewItemIdGetResponseGetItemApiV1ReviewItemsReviewItemIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            review_item_id=review_item_id,
            client=client,
        )
    ).parsed
