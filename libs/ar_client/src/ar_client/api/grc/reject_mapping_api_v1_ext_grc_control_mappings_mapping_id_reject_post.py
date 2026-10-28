from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.reject_mapping_api_v1_ext_grc_control_mappings_mapping_id_reject_post_response_reject_mapping_api_v1_ext_grc_control_mappings_mapping_id_reject_post import (
    RejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPostResponseRejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    mapping_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/control-mappings/{mapping_id}:reject".format(
            mapping_id=quote(str(mapping_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | RejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPostResponseRejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPost
    | None
):
    if response.status_code == 200:
        response_200 = RejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPostResponseRejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPost.from_dict(
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
    | RejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPostResponseRejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPost
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
    HTTPValidationError
    | RejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPostResponseRejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPost
]:
    """Reject Mapping

    Args:
        mapping_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPostResponseRejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPost]
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
    HTTPValidationError
    | RejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPostResponseRejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPost
    | None
):
    """Reject Mapping

    Args:
        mapping_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPostResponseRejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPost
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
    HTTPValidationError
    | RejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPostResponseRejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPost
]:
    """Reject Mapping

    Args:
        mapping_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPostResponseRejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPost]
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
    HTTPValidationError
    | RejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPostResponseRejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPost
    | None
):
    """Reject Mapping

    Args:
        mapping_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPostResponseRejectMappingApiV1ExtGrcControlMappingsMappingIdRejectPost
    """

    return (
        await asyncio_detailed(
            mapping_id=mapping_id,
            client=client,
        )
    ).parsed
