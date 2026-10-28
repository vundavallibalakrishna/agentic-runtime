from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_framework_api_v1_ext_grc_frameworks_framework_id_get_response_get_framework_api_v1_ext_grc_frameworks_framework_id_get import (
    GetFrameworkApiV1ExtGrcFrameworksFrameworkIdGetResponseGetFrameworkApiV1ExtGrcFrameworksFrameworkIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    framework_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/frameworks/{framework_id}".format(
            framework_id=quote(str(framework_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetFrameworkApiV1ExtGrcFrameworksFrameworkIdGetResponseGetFrameworkApiV1ExtGrcFrameworksFrameworkIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetFrameworkApiV1ExtGrcFrameworksFrameworkIdGetResponseGetFrameworkApiV1ExtGrcFrameworksFrameworkIdGet.from_dict(
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
    GetFrameworkApiV1ExtGrcFrameworksFrameworkIdGetResponseGetFrameworkApiV1ExtGrcFrameworksFrameworkIdGet
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
    GetFrameworkApiV1ExtGrcFrameworksFrameworkIdGetResponseGetFrameworkApiV1ExtGrcFrameworksFrameworkIdGet
    | HTTPValidationError
]:
    """Get Framework

    Args:
        framework_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetFrameworkApiV1ExtGrcFrameworksFrameworkIdGetResponseGetFrameworkApiV1ExtGrcFrameworksFrameworkIdGet | HTTPValidationError]
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
    GetFrameworkApiV1ExtGrcFrameworksFrameworkIdGetResponseGetFrameworkApiV1ExtGrcFrameworksFrameworkIdGet
    | HTTPValidationError
    | None
):
    """Get Framework

    Args:
        framework_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetFrameworkApiV1ExtGrcFrameworksFrameworkIdGetResponseGetFrameworkApiV1ExtGrcFrameworksFrameworkIdGet | HTTPValidationError
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
    GetFrameworkApiV1ExtGrcFrameworksFrameworkIdGetResponseGetFrameworkApiV1ExtGrcFrameworksFrameworkIdGet
    | HTTPValidationError
]:
    """Get Framework

    Args:
        framework_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetFrameworkApiV1ExtGrcFrameworksFrameworkIdGetResponseGetFrameworkApiV1ExtGrcFrameworksFrameworkIdGet | HTTPValidationError]
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
    GetFrameworkApiV1ExtGrcFrameworksFrameworkIdGetResponseGetFrameworkApiV1ExtGrcFrameworksFrameworkIdGet
    | HTTPValidationError
    | None
):
    """Get Framework

    Args:
        framework_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetFrameworkApiV1ExtGrcFrameworksFrameworkIdGetResponseGetFrameworkApiV1ExtGrcFrameworksFrameworkIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            framework_id=framework_id,
            client=client,
        )
    ).parsed
