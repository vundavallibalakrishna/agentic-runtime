from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.test_install_api_v1_connector_installs_install_id_test_post_response_test_install_api_v1_connector_installs_install_id_test_post import (
    TestInstallApiV1ConnectorInstallsInstallIdTestPostResponseTestInstallApiV1ConnectorInstallsInstallIdTestPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    install_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/connector-installs/{install_id}:test".format(
            install_id=quote(str(install_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | TestInstallApiV1ConnectorInstallsInstallIdTestPostResponseTestInstallApiV1ConnectorInstallsInstallIdTestPost
    | None
):
    if response.status_code == 200:
        response_200 = TestInstallApiV1ConnectorInstallsInstallIdTestPostResponseTestInstallApiV1ConnectorInstallsInstallIdTestPost.from_dict(
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
    | TestInstallApiV1ConnectorInstallsInstallIdTestPostResponseTestInstallApiV1ConnectorInstallsInstallIdTestPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    install_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | TestInstallApiV1ConnectorInstallsInstallIdTestPostResponseTestInstallApiV1ConnectorInstallsInstallIdTestPost
]:
    """Test Install

    Args:
        install_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | TestInstallApiV1ConnectorInstallsInstallIdTestPostResponseTestInstallApiV1ConnectorInstallsInstallIdTestPost]
    """

    kwargs = _get_kwargs(
        install_id=install_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    install_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | TestInstallApiV1ConnectorInstallsInstallIdTestPostResponseTestInstallApiV1ConnectorInstallsInstallIdTestPost
    | None
):
    """Test Install

    Args:
        install_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | TestInstallApiV1ConnectorInstallsInstallIdTestPostResponseTestInstallApiV1ConnectorInstallsInstallIdTestPost
    """

    return sync_detailed(
        install_id=install_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    install_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | TestInstallApiV1ConnectorInstallsInstallIdTestPostResponseTestInstallApiV1ConnectorInstallsInstallIdTestPost
]:
    """Test Install

    Args:
        install_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | TestInstallApiV1ConnectorInstallsInstallIdTestPostResponseTestInstallApiV1ConnectorInstallsInstallIdTestPost]
    """

    kwargs = _get_kwargs(
        install_id=install_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    install_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | TestInstallApiV1ConnectorInstallsInstallIdTestPostResponseTestInstallApiV1ConnectorInstallsInstallIdTestPost
    | None
):
    """Test Install

    Args:
        install_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | TestInstallApiV1ConnectorInstallsInstallIdTestPostResponseTestInstallApiV1ConnectorInstallsInstallIdTestPost
    """

    return (
        await asyncio_detailed(
            install_id=install_id,
            client=client,
        )
    ).parsed
