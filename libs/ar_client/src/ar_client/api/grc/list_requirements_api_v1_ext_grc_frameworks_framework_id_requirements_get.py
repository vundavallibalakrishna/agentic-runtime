from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_requirements_api_v1_ext_grc_frameworks_framework_id_requirements_get_response_list_requirements_api_v1_ext_grc_frameworks_framework_id_requirements_get import (
    ListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGetResponseListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGet,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    framework_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/frameworks/{framework_id}/requirements".format(
            framework_id=quote(str(framework_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGetResponseListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGet
    | None
):
    if response.status_code == 200:
        response_200 = ListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGetResponseListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGet.from_dict(
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
    | ListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGetResponseListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGet
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
    HTTPValidationError
    | ListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGetResponseListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGet
]:
    """List Requirements

    Args:
        framework_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGetResponseListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGet]
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
    HTTPValidationError
    | ListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGetResponseListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGet
    | None
):
    """List Requirements

    Args:
        framework_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGetResponseListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGet
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
    HTTPValidationError
    | ListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGetResponseListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGet
]:
    """List Requirements

    Args:
        framework_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGetResponseListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGet]
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
    HTTPValidationError
    | ListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGetResponseListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGet
    | None
):
    """List Requirements

    Args:
        framework_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGetResponseListRequirementsApiV1ExtGrcFrameworksFrameworkIdRequirementsGet
    """

    return (
        await asyncio_detailed(
            framework_id=framework_id,
            client=client,
        )
    ).parsed
