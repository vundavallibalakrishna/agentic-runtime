from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.export_oscal_api_v1_ext_grc_frameworks_framework_id_export_oscal_get_response_export_oscal_api_v1_ext_grc_frameworks_framework_id_export_oscal_get import (
    ExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGetResponseExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    framework_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/frameworks/{framework_id}:export-oscal".format(
            framework_id=quote(str(framework_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGetResponseExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = ExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGetResponseExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGet.from_dict(
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
    ExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGetResponseExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    framework_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGetResponseExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGet
    | HTTPValidationError
]:
    """Export Oscal

    Args:
        framework_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGetResponseExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        framework_id=framework_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    framework_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    ExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGetResponseExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGet
    | HTTPValidationError
    | None
):
    """Export Oscal

    Args:
        framework_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGetResponseExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGet | HTTPValidationError
    """

    return sync_detailed(
        framework_id=framework_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    framework_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGetResponseExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGet
    | HTTPValidationError
]:
    """Export Oscal

    Args:
        framework_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGetResponseExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        framework_id=framework_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    framework_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    ExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGetResponseExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGet
    | HTTPValidationError
    | None
):
    """Export Oscal

    Args:
        framework_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGetResponseExportOscalApiV1ExtGrcFrameworksFrameworkIdExportOscalGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            framework_id=framework_id,
            client=client,
        )
    ).parsed
