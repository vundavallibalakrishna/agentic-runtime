from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.item_body import ItemBody
from ...models.open_item_api_v1_review_items_post_response_open_item_api_v1_review_items_post import (
    OpenItemApiV1ReviewItemsPostResponseOpenItemApiV1ReviewItemsPost,
)
from typing import cast


def _get_kwargs(
    *,
    body: ItemBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/review-items",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | OpenItemApiV1ReviewItemsPostResponseOpenItemApiV1ReviewItemsPost | None:
    if response.status_code == 200:
        response_200 = OpenItemApiV1ReviewItemsPostResponseOpenItemApiV1ReviewItemsPost.from_dict(
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
    HTTPValidationError | OpenItemApiV1ReviewItemsPostResponseOpenItemApiV1ReviewItemsPost
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
    body: ItemBody,
) -> Response[
    HTTPValidationError | OpenItemApiV1ReviewItemsPostResponseOpenItemApiV1ReviewItemsPost
]:
    """Open Item

    Args:
        body (ItemBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OpenItemApiV1ReviewItemsPostResponseOpenItemApiV1ReviewItemsPost]
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
    body: ItemBody,
) -> HTTPValidationError | OpenItemApiV1ReviewItemsPostResponseOpenItemApiV1ReviewItemsPost | None:
    """Open Item

    Args:
        body (ItemBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OpenItemApiV1ReviewItemsPostResponseOpenItemApiV1ReviewItemsPost
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ItemBody,
) -> Response[
    HTTPValidationError | OpenItemApiV1ReviewItemsPostResponseOpenItemApiV1ReviewItemsPost
]:
    """Open Item

    Args:
        body (ItemBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OpenItemApiV1ReviewItemsPostResponseOpenItemApiV1ReviewItemsPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: ItemBody,
) -> HTTPValidationError | OpenItemApiV1ReviewItemsPostResponseOpenItemApiV1ReviewItemsPost | None:
    """Open Item

    Args:
        body (ItemBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OpenItemApiV1ReviewItemsPostResponseOpenItemApiV1ReviewItemsPost
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
