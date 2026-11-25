from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.save_settings_api_v1_resource_settings_resource_type_resource_id_put_response_save_settings_api_v1_resource_settings_resource_type_resource_id_put import (
    SaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPutResponseSaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPut,
)
from ...models.settings_body import SettingsBody
from typing import cast


def _get_kwargs(
    resource_type: str,
    resource_id: str,
    *,
    body: SettingsBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/api/v1/resource-settings/{resource_type}/{resource_id}".format(
            resource_type=quote(str(resource_type), safe=""),
            resource_id=quote(str(resource_id), safe=""),
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
    | SaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPutResponseSaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPut
    | None
):
    if response.status_code == 200:
        response_200 = SaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPutResponseSaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPut.from_dict(
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
    | SaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPutResponseSaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPut
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
    body: SettingsBody,
) -> Response[
    HTTPValidationError
    | SaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPutResponseSaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPut
]:
    """Save Settings

    Args:
        resource_type (str):
        resource_id (str):
        body (SettingsBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPutResponseSaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPut]
    """

    kwargs = _get_kwargs(
        resource_type=resource_type,
        resource_id=resource_id,
        body=body,
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
    body: SettingsBody,
) -> (
    HTTPValidationError
    | SaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPutResponseSaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPut
    | None
):
    """Save Settings

    Args:
        resource_type (str):
        resource_id (str):
        body (SettingsBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPutResponseSaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPut
    """

    return sync_detailed(
        resource_type=resource_type,
        resource_id=resource_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    resource_type: str,
    resource_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: SettingsBody,
) -> Response[
    HTTPValidationError
    | SaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPutResponseSaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPut
]:
    """Save Settings

    Args:
        resource_type (str):
        resource_id (str):
        body (SettingsBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPutResponseSaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPut]
    """

    kwargs = _get_kwargs(
        resource_type=resource_type,
        resource_id=resource_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    resource_type: str,
    resource_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: SettingsBody,
) -> (
    HTTPValidationError
    | SaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPutResponseSaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPut
    | None
):
    """Save Settings

    Args:
        resource_type (str):
        resource_id (str):
        body (SettingsBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPutResponseSaveSettingsApiV1ResourceSettingsResourceTypeResourceIdPut
    """

    return (
        await asyncio_detailed(
            resource_type=resource_type,
            resource_id=resource_id,
            client=client,
            body=body,
        )
    ).parsed
