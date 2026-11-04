from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.connector_install_body import ConnectorInstallBody
from ...models.http_validation_error import HTTPValidationError
from ...models.install_connector_api_v1_connectors_slug_install_post_response_install_connector_api_v1_connectors_slug_install_post import (
    InstallConnectorApiV1ConnectorsSlugInstallPostResponseInstallConnectorApiV1ConnectorsSlugInstallPost,
)
from typing import cast


def _get_kwargs(
    slug: str,
    *,
    body: ConnectorInstallBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/connectors/{slug}:install".format(
            slug=quote(str(slug), safe=""),
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
    | InstallConnectorApiV1ConnectorsSlugInstallPostResponseInstallConnectorApiV1ConnectorsSlugInstallPost
    | None
):
    if response.status_code == 200:
        response_200 = InstallConnectorApiV1ConnectorsSlugInstallPostResponseInstallConnectorApiV1ConnectorsSlugInstallPost.from_dict(
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
    | InstallConnectorApiV1ConnectorsSlugInstallPostResponseInstallConnectorApiV1ConnectorsSlugInstallPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    slug: str,
    *,
    client: AuthenticatedClient | Client,
    body: ConnectorInstallBody,
) -> Response[
    HTTPValidationError
    | InstallConnectorApiV1ConnectorsSlugInstallPostResponseInstallConnectorApiV1ConnectorsSlugInstallPost
]:
    """Install Connector

    Args:
        slug (str):
        body (ConnectorInstallBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | InstallConnectorApiV1ConnectorsSlugInstallPostResponseInstallConnectorApiV1ConnectorsSlugInstallPost]
    """

    kwargs = _get_kwargs(
        slug=slug,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    slug: str,
    *,
    client: AuthenticatedClient | Client,
    body: ConnectorInstallBody,
) -> (
    HTTPValidationError
    | InstallConnectorApiV1ConnectorsSlugInstallPostResponseInstallConnectorApiV1ConnectorsSlugInstallPost
    | None
):
    """Install Connector

    Args:
        slug (str):
        body (ConnectorInstallBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | InstallConnectorApiV1ConnectorsSlugInstallPostResponseInstallConnectorApiV1ConnectorsSlugInstallPost
    """

    return sync_detailed(
        slug=slug,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    slug: str,
    *,
    client: AuthenticatedClient | Client,
    body: ConnectorInstallBody,
) -> Response[
    HTTPValidationError
    | InstallConnectorApiV1ConnectorsSlugInstallPostResponseInstallConnectorApiV1ConnectorsSlugInstallPost
]:
    """Install Connector

    Args:
        slug (str):
        body (ConnectorInstallBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | InstallConnectorApiV1ConnectorsSlugInstallPostResponseInstallConnectorApiV1ConnectorsSlugInstallPost]
    """

    kwargs = _get_kwargs(
        slug=slug,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    slug: str,
    *,
    client: AuthenticatedClient | Client,
    body: ConnectorInstallBody,
) -> (
    HTTPValidationError
    | InstallConnectorApiV1ConnectorsSlugInstallPostResponseInstallConnectorApiV1ConnectorsSlugInstallPost
    | None
):
    """Install Connector

    Args:
        slug (str):
        body (ConnectorInstallBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | InstallConnectorApiV1ConnectorsSlugInstallPostResponseInstallConnectorApiV1ConnectorsSlugInstallPost
    """

    return (
        await asyncio_detailed(
            slug=slug,
            client=client,
            body=body,
        )
    ).parsed
