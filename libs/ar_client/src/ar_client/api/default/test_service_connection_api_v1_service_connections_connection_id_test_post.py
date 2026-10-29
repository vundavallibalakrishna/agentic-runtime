from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.connection_test_body import ConnectionTestBody
from ...models.http_validation_error import HTTPValidationError
from ...models.test_service_connection_api_v1_service_connections_connection_id_test_post_response_test_service_connection_api_v1_service_connections_connection_id_test_post import (
    TestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPostResponseTestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    connection_id: UUID,
    *,
    body: ConnectionTestBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/service-connections/{connection_id}:test".format(
            connection_id=quote(str(connection_id), safe=""),
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
    | TestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPostResponseTestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPost
    | None
):
    if response.status_code == 200:
        response_200 = TestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPostResponseTestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPost.from_dict(
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
    | TestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPostResponseTestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ConnectionTestBody,
) -> Response[
    HTTPValidationError
    | TestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPostResponseTestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPost
]:
    """Test Service Connection

    Args:
        connection_id (UUID):
        body (ConnectionTestBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | TestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPostResponseTestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPost]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ConnectionTestBody,
) -> (
    HTTPValidationError
    | TestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPostResponseTestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPost
    | None
):
    """Test Service Connection

    Args:
        connection_id (UUID):
        body (ConnectionTestBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | TestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPostResponseTestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPost
    """

    return sync_detailed(
        connection_id=connection_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ConnectionTestBody,
) -> Response[
    HTTPValidationError
    | TestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPostResponseTestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPost
]:
    """Test Service Connection

    Args:
        connection_id (UUID):
        body (ConnectionTestBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | TestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPostResponseTestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPost]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ConnectionTestBody,
) -> (
    HTTPValidationError
    | TestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPostResponseTestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPost
    | None
):
    """Test Service Connection

    Args:
        connection_id (UUID):
        body (ConnectionTestBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | TestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPostResponseTestServiceConnectionApiV1ServiceConnectionsConnectionIdTestPost
    """

    return (
        await asyncio_detailed(
            connection_id=connection_id,
            client=client,
            body=body,
        )
    ).parsed
