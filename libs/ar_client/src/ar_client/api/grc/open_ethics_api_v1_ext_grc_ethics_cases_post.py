from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.open_ethics_api_v1_ext_grc_ethics_cases_post_body import (
    OpenEthicsApiV1ExtGrcEthicsCasesPostBody,
)
from ...models.open_ethics_api_v1_ext_grc_ethics_cases_post_response_open_ethics_api_v1_ext_grc_ethics_cases_post import (
    OpenEthicsApiV1ExtGrcEthicsCasesPostResponseOpenEthicsApiV1ExtGrcEthicsCasesPost,
)
from typing import cast


def _get_kwargs(
    *,
    body: OpenEthicsApiV1ExtGrcEthicsCasesPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/ethics-cases",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | OpenEthicsApiV1ExtGrcEthicsCasesPostResponseOpenEthicsApiV1ExtGrcEthicsCasesPost
    | None
):
    if response.status_code == 200:
        response_200 = OpenEthicsApiV1ExtGrcEthicsCasesPostResponseOpenEthicsApiV1ExtGrcEthicsCasesPost.from_dict(
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
    | OpenEthicsApiV1ExtGrcEthicsCasesPostResponseOpenEthicsApiV1ExtGrcEthicsCasesPost
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
    body: OpenEthicsApiV1ExtGrcEthicsCasesPostBody,
) -> Response[
    HTTPValidationError
    | OpenEthicsApiV1ExtGrcEthicsCasesPostResponseOpenEthicsApiV1ExtGrcEthicsCasesPost
]:
    """Open Ethics

    Args:
        body (OpenEthicsApiV1ExtGrcEthicsCasesPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OpenEthicsApiV1ExtGrcEthicsCasesPostResponseOpenEthicsApiV1ExtGrcEthicsCasesPost]
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
    body: OpenEthicsApiV1ExtGrcEthicsCasesPostBody,
) -> (
    HTTPValidationError
    | OpenEthicsApiV1ExtGrcEthicsCasesPostResponseOpenEthicsApiV1ExtGrcEthicsCasesPost
    | None
):
    """Open Ethics

    Args:
        body (OpenEthicsApiV1ExtGrcEthicsCasesPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OpenEthicsApiV1ExtGrcEthicsCasesPostResponseOpenEthicsApiV1ExtGrcEthicsCasesPost
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: OpenEthicsApiV1ExtGrcEthicsCasesPostBody,
) -> Response[
    HTTPValidationError
    | OpenEthicsApiV1ExtGrcEthicsCasesPostResponseOpenEthicsApiV1ExtGrcEthicsCasesPost
]:
    """Open Ethics

    Args:
        body (OpenEthicsApiV1ExtGrcEthicsCasesPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | OpenEthicsApiV1ExtGrcEthicsCasesPostResponseOpenEthicsApiV1ExtGrcEthicsCasesPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: OpenEthicsApiV1ExtGrcEthicsCasesPostBody,
) -> (
    HTTPValidationError
    | OpenEthicsApiV1ExtGrcEthicsCasesPostResponseOpenEthicsApiV1ExtGrcEthicsCasesPost
    | None
):
    """Open Ethics

    Args:
        body (OpenEthicsApiV1ExtGrcEthicsCasesPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | OpenEthicsApiV1ExtGrcEthicsCasesPostResponseOpenEthicsApiV1ExtGrcEthicsCasesPost
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
