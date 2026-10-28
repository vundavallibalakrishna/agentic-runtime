from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_obligation_api_v1_ext_grc_obligations_post_body import (
    CreateObligationApiV1ExtGrcObligationsPostBody,
)
from ...models.create_obligation_api_v1_ext_grc_obligations_post_response_create_obligation_api_v1_ext_grc_obligations_post import (
    CreateObligationApiV1ExtGrcObligationsPostResponseCreateObligationApiV1ExtGrcObligationsPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    *,
    body: CreateObligationApiV1ExtGrcObligationsPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/obligations",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateObligationApiV1ExtGrcObligationsPostResponseCreateObligationApiV1ExtGrcObligationsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CreateObligationApiV1ExtGrcObligationsPostResponseCreateObligationApiV1ExtGrcObligationsPost.from_dict(
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
    CreateObligationApiV1ExtGrcObligationsPostResponseCreateObligationApiV1ExtGrcObligationsPost
    | HTTPValidationError
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
    body: CreateObligationApiV1ExtGrcObligationsPostBody,
) -> Response[
    CreateObligationApiV1ExtGrcObligationsPostResponseCreateObligationApiV1ExtGrcObligationsPost
    | HTTPValidationError
]:
    """Create Obligation

    Args:
        body (CreateObligationApiV1ExtGrcObligationsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateObligationApiV1ExtGrcObligationsPostResponseCreateObligationApiV1ExtGrcObligationsPost | HTTPValidationError]
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
    body: CreateObligationApiV1ExtGrcObligationsPostBody,
) -> (
    CreateObligationApiV1ExtGrcObligationsPostResponseCreateObligationApiV1ExtGrcObligationsPost
    | HTTPValidationError
    | None
):
    """Create Obligation

    Args:
        body (CreateObligationApiV1ExtGrcObligationsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateObligationApiV1ExtGrcObligationsPostResponseCreateObligationApiV1ExtGrcObligationsPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateObligationApiV1ExtGrcObligationsPostBody,
) -> Response[
    CreateObligationApiV1ExtGrcObligationsPostResponseCreateObligationApiV1ExtGrcObligationsPost
    | HTTPValidationError
]:
    """Create Obligation

    Args:
        body (CreateObligationApiV1ExtGrcObligationsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateObligationApiV1ExtGrcObligationsPostResponseCreateObligationApiV1ExtGrcObligationsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: CreateObligationApiV1ExtGrcObligationsPostBody,
) -> (
    CreateObligationApiV1ExtGrcObligationsPostResponseCreateObligationApiV1ExtGrcObligationsPost
    | HTTPValidationError
    | None
):
    """Create Obligation

    Args:
        body (CreateObligationApiV1ExtGrcObligationsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateObligationApiV1ExtGrcObligationsPostResponseCreateObligationApiV1ExtGrcObligationsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
