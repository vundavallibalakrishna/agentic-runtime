from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_service_account_api_v1_service_accounts_service_account_id_delete_response_delete_service_account_api_v1_service_accounts_service_account_id_delete import (
    DeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDeleteResponseDeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    service_account_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/service-accounts/{service_account_id}".format(
            service_account_id=quote(str(service_account_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDeleteResponseDeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDeleteResponseDeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDelete.from_dict(
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
    DeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDeleteResponseDeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDelete
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    service_account_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDeleteResponseDeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDelete
    | HTTPValidationError
]:
    """Delete Service Account

    Args:
        service_account_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDeleteResponseDeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        service_account_id=service_account_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    service_account_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDeleteResponseDeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDelete
    | HTTPValidationError
    | None
):
    """Delete Service Account

    Args:
        service_account_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDeleteResponseDeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDelete | HTTPValidationError
    """

    return sync_detailed(
        service_account_id=service_account_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    service_account_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDeleteResponseDeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDelete
    | HTTPValidationError
]:
    """Delete Service Account

    Args:
        service_account_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDeleteResponseDeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        service_account_id=service_account_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    service_account_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDeleteResponseDeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDelete
    | HTTPValidationError
    | None
):
    """Delete Service Account

    Args:
        service_account_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDeleteResponseDeleteServiceAccountApiV1ServiceAccountsServiceAccountIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            service_account_id=service_account_id,
            client=client,
        )
    ).parsed
