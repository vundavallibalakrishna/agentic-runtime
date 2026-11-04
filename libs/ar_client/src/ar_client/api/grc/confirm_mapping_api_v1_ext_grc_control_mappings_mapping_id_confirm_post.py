from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.confirm_mapping_api_v1_ext_grc_control_mappings_mapping_id_confirm_post_response_confirm_mapping_api_v1_ext_grc_control_mappings_mapping_id_confirm_post import (
    ConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPostResponseConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    mapping_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/control-mappings/{mapping_id}:confirm".format(
            mapping_id=quote(str(mapping_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPostResponseConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = ConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPostResponseConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPost.from_dict(
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
    ConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPostResponseConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    mapping_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPostResponseConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPost
    | HTTPValidationError
]:
    """Confirm Mapping

    Args:
        mapping_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPostResponseConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        mapping_id=mapping_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    mapping_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    ConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPostResponseConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPost
    | HTTPValidationError
    | None
):
    """Confirm Mapping

    Args:
        mapping_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPostResponseConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPost | HTTPValidationError
    """

    return sync_detailed(
        mapping_id=mapping_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    mapping_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPostResponseConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPost
    | HTTPValidationError
]:
    """Confirm Mapping

    Args:
        mapping_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPostResponseConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        mapping_id=mapping_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    mapping_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    ConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPostResponseConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPost
    | HTTPValidationError
    | None
):
    """Confirm Mapping

    Args:
        mapping_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPostResponseConfirmMappingApiV1ExtGrcControlMappingsMappingIdConfirmPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            mapping_id=mapping_id,
            client=client,
        )
    ).parsed
