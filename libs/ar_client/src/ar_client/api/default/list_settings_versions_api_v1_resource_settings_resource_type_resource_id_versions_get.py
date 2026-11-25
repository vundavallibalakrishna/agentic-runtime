from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_settings_versions_api_v1_resource_settings_resource_type_resource_id_versions_get_response_list_settings_versions_api_v1_resource_settings_resource_type_resource_id_versions_get import (
    ListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGetResponseListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGet,
)
from typing import cast


def _get_kwargs(
    resource_type: str,
    resource_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/resource-settings/{resource_type}/{resource_id}/versions".format(
            resource_type=quote(str(resource_type), safe=""),
            resource_id=quote(str(resource_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGetResponseListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGet
    | None
):
    if response.status_code == 200:
        response_200 = ListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGetResponseListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGet.from_dict(
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
    | ListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGetResponseListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGet
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    resource_type: str,
    resource_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | ListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGetResponseListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGet
]:
    """List Settings Versions

    Args:
        resource_type (str):
        resource_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGetResponseListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGet]
    """

    kwargs = _get_kwargs(
        resource_type=resource_type,
        resource_id=resource_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    resource_type: str,
    resource_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | ListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGetResponseListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGet
    | None
):
    """List Settings Versions

    Args:
        resource_type (str):
        resource_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGetResponseListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGet
    """

    return sync_detailed(
        resource_type=resource_type,
        resource_id=resource_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    resource_type: str,
    resource_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | ListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGetResponseListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGet
]:
    """List Settings Versions

    Args:
        resource_type (str):
        resource_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGetResponseListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGet]
    """

    kwargs = _get_kwargs(
        resource_type=resource_type,
        resource_id=resource_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    resource_type: str,
    resource_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | ListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGetResponseListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGet
    | None
):
    """List Settings Versions

    Args:
        resource_type (str):
        resource_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGetResponseListSettingsVersionsApiV1ResourceSettingsResourceTypeResourceIdVersionsGet
    """

    return (
        await asyncio_detailed(
            resource_type=resource_type,
            resource_id=resource_id,
            client=client,
        )
    ).parsed
