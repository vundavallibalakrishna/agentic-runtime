from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_control_api_v1_ext_grc_controls_control_id_get_response_get_control_api_v1_ext_grc_controls_control_id_get import (
    GetControlApiV1ExtGrcControlsControlIdGetResponseGetControlApiV1ExtGrcControlsControlIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    control_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/controls/{control_id}".format(
            control_id=quote(str(control_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetControlApiV1ExtGrcControlsControlIdGetResponseGetControlApiV1ExtGrcControlsControlIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetControlApiV1ExtGrcControlsControlIdGetResponseGetControlApiV1ExtGrcControlsControlIdGet.from_dict(
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
    GetControlApiV1ExtGrcControlsControlIdGetResponseGetControlApiV1ExtGrcControlsControlIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    control_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetControlApiV1ExtGrcControlsControlIdGetResponseGetControlApiV1ExtGrcControlsControlIdGet
    | HTTPValidationError
]:
    """Get Control

    Args:
        control_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetControlApiV1ExtGrcControlsControlIdGetResponseGetControlApiV1ExtGrcControlsControlIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        control_id=control_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    control_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetControlApiV1ExtGrcControlsControlIdGetResponseGetControlApiV1ExtGrcControlsControlIdGet
    | HTTPValidationError
    | None
):
    """Get Control

    Args:
        control_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetControlApiV1ExtGrcControlsControlIdGetResponseGetControlApiV1ExtGrcControlsControlIdGet | HTTPValidationError
    """

    return sync_detailed(
        control_id=control_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    control_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetControlApiV1ExtGrcControlsControlIdGetResponseGetControlApiV1ExtGrcControlsControlIdGet
    | HTTPValidationError
]:
    """Get Control

    Args:
        control_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetControlApiV1ExtGrcControlsControlIdGetResponseGetControlApiV1ExtGrcControlsControlIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        control_id=control_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    control_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetControlApiV1ExtGrcControlsControlIdGetResponseGetControlApiV1ExtGrcControlsControlIdGet
    | HTTPValidationError
    | None
):
    """Get Control

    Args:
        control_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetControlApiV1ExtGrcControlsControlIdGetResponseGetControlApiV1ExtGrcControlsControlIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            control_id=control_id,
            client=client,
        )
    ).parsed
