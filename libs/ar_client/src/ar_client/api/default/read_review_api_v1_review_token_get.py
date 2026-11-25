from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.read_review_api_v1_review_token_get_response_read_review_api_v1_review_token_get import (
    ReadReviewApiV1ReviewTokenGetResponseReadReviewApiV1ReviewTokenGet,
)
from typing import cast


def _get_kwargs(
    token: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/review/{token}".format(
            token=quote(str(token), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError | ReadReviewApiV1ReviewTokenGetResponseReadReviewApiV1ReviewTokenGet | None
):
    if response.status_code == 200:
        response_200 = ReadReviewApiV1ReviewTokenGetResponseReadReviewApiV1ReviewTokenGet.from_dict(
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
    HTTPValidationError | ReadReviewApiV1ReviewTokenGetResponseReadReviewApiV1ReviewTokenGet
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
) -> Response[
    HTTPValidationError | ReadReviewApiV1ReviewTokenGetResponseReadReviewApiV1ReviewTokenGet
]:
    """Read Review

     The one approval this link names. Other approvals are not returned.

    Args:
        token (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ReadReviewApiV1ReviewTokenGetResponseReadReviewApiV1ReviewTokenGet]
    """

    kwargs = _get_kwargs(
        token=token,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    token: str,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError | ReadReviewApiV1ReviewTokenGetResponseReadReviewApiV1ReviewTokenGet | None
):
    """Read Review

     The one approval this link names. Other approvals are not returned.

    Args:
        token (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ReadReviewApiV1ReviewTokenGetResponseReadReviewApiV1ReviewTokenGet
    """

    return sync_detailed(
        token=token,
        client=client,
    ).parsed


async def asyncio_detailed(
    token: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError | ReadReviewApiV1ReviewTokenGetResponseReadReviewApiV1ReviewTokenGet
]:
    """Read Review

     The one approval this link names. Other approvals are not returned.

    Args:
        token (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ReadReviewApiV1ReviewTokenGetResponseReadReviewApiV1ReviewTokenGet]
    """

    kwargs = _get_kwargs(
        token=token,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    token: str,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError | ReadReviewApiV1ReviewTokenGetResponseReadReviewApiV1ReviewTokenGet | None
):
    """Read Review

     The one approval this link names. Other approvals are not returned.

    Args:
        token (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ReadReviewApiV1ReviewTokenGetResponseReadReviewApiV1ReviewTokenGet
    """

    return (
        await asyncio_detailed(
            token=token,
            client=client,
        )
    ).parsed
