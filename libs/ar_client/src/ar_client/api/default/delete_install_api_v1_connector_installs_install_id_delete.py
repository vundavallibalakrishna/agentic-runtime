from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_install_api_v1_connector_installs_install_id_delete_response_delete_install_api_v1_connector_installs_install_id_delete import (
    DeleteInstallApiV1ConnectorInstallsInstallIdDeleteResponseDeleteInstallApiV1ConnectorInstallsInstallIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    install_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/connector-installs/{install_id}".format(
            install_id=quote(str(install_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeleteInstallApiV1ConnectorInstallsInstallIdDeleteResponseDeleteInstallApiV1ConnectorInstallsInstallIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DeleteInstallApiV1ConnectorInstallsInstallIdDeleteResponseDeleteInstallApiV1ConnectorInstallsInstallIdDelete.from_dict(
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
    DeleteInstallApiV1ConnectorInstallsInstallIdDeleteResponseDeleteInstallApiV1ConnectorInstallsInstallIdDelete
    | HTTPValidationError
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
    DeleteInstallApiV1ConnectorInstallsInstallIdDeleteResponseDeleteInstallApiV1ConnectorInstallsInstallIdDelete
    | HTTPValidationError
]:
    """Delete Install

    Args:
        install_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteInstallApiV1ConnectorInstallsInstallIdDeleteResponseDeleteInstallApiV1ConnectorInstallsInstallIdDelete | HTTPValidationError]
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
    DeleteInstallApiV1ConnectorInstallsInstallIdDeleteResponseDeleteInstallApiV1ConnectorInstallsInstallIdDelete
    | HTTPValidationError
    | None
):
    """Delete Install

    Args:
        install_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteInstallApiV1ConnectorInstallsInstallIdDeleteResponseDeleteInstallApiV1ConnectorInstallsInstallIdDelete | HTTPValidationError
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
    DeleteInstallApiV1ConnectorInstallsInstallIdDeleteResponseDeleteInstallApiV1ConnectorInstallsInstallIdDelete
    | HTTPValidationError
]:
    """Delete Install

    Args:
        install_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteInstallApiV1ConnectorInstallsInstallIdDeleteResponseDeleteInstallApiV1ConnectorInstallsInstallIdDelete | HTTPValidationError]
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
    DeleteInstallApiV1ConnectorInstallsInstallIdDeleteResponseDeleteInstallApiV1ConnectorInstallsInstallIdDelete
    | HTTPValidationError
    | None
):
    """Delete Install

    Args:
        install_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteInstallApiV1ConnectorInstallsInstallIdDeleteResponseDeleteInstallApiV1ConnectorInstallsInstallIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            install_id=install_id,
            client=client,
        )
    ).parsed
