from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.constraint_body import ConstraintBody
from ...models.create_constraint_api_v1_sod_constraints_post_response_create_constraint_api_v1_sod_constraints_post import (
    CreateConstraintApiV1SodConstraintsPostResponseCreateConstraintApiV1SodConstraintsPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    *,
    body: ConstraintBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/sod-constraints",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateConstraintApiV1SodConstraintsPostResponseCreateConstraintApiV1SodConstraintsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CreateConstraintApiV1SodConstraintsPostResponseCreateConstraintApiV1SodConstraintsPost.from_dict(
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
    CreateConstraintApiV1SodConstraintsPostResponseCreateConstraintApiV1SodConstraintsPost
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
    body: ConstraintBody,
) -> Response[
    CreateConstraintApiV1SodConstraintsPostResponseCreateConstraintApiV1SodConstraintsPost
    | HTTPValidationError
]:
    """Create Constraint

    Args:
        body (ConstraintBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateConstraintApiV1SodConstraintsPostResponseCreateConstraintApiV1SodConstraintsPost | HTTPValidationError]
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
    body: ConstraintBody,
) -> (
    CreateConstraintApiV1SodConstraintsPostResponseCreateConstraintApiV1SodConstraintsPost
    | HTTPValidationError
    | None
):
    """Create Constraint

    Args:
        body (ConstraintBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateConstraintApiV1SodConstraintsPostResponseCreateConstraintApiV1SodConstraintsPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ConstraintBody,
) -> Response[
    CreateConstraintApiV1SodConstraintsPostResponseCreateConstraintApiV1SodConstraintsPost
    | HTTPValidationError
]:
    """Create Constraint

    Args:
        body (ConstraintBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateConstraintApiV1SodConstraintsPostResponseCreateConstraintApiV1SodConstraintsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: ConstraintBody,
) -> (
    CreateConstraintApiV1SodConstraintsPostResponseCreateConstraintApiV1SodConstraintsPost
    | HTTPValidationError
    | None
):
    """Create Constraint

    Args:
        body (ConstraintBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateConstraintApiV1SodConstraintsPostResponseCreateConstraintApiV1SodConstraintsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
