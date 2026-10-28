from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.build_binder_api_v1_binders_binder_id_build_post_response_build_binder_api_v1_binders_binder_id_build_post import (
    BuildBinderApiV1BindersBinderIdBuildPostResponseBuildBinderApiV1BindersBinderIdBuildPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    binder_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/binders/{binder_id}:build".format(
            binder_id=quote(str(binder_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    BuildBinderApiV1BindersBinderIdBuildPostResponseBuildBinderApiV1BindersBinderIdBuildPost
    | HTTPValidationError
    | None
):
    if response.status_code == 202:
        response_202 = BuildBinderApiV1BindersBinderIdBuildPostResponseBuildBinderApiV1BindersBinderIdBuildPost.from_dict(
            response.json()
        )

        return response_202

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
    BuildBinderApiV1BindersBinderIdBuildPostResponseBuildBinderApiV1BindersBinderIdBuildPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    binder_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    BuildBinderApiV1BindersBinderIdBuildPostResponseBuildBinderApiV1BindersBinderIdBuildPost
    | HTTPValidationError
]:
    """Build Binder

    Args:
        binder_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[BuildBinderApiV1BindersBinderIdBuildPostResponseBuildBinderApiV1BindersBinderIdBuildPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        binder_id=binder_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    binder_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    BuildBinderApiV1BindersBinderIdBuildPostResponseBuildBinderApiV1BindersBinderIdBuildPost
    | HTTPValidationError
    | None
):
    """Build Binder

    Args:
        binder_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        BuildBinderApiV1BindersBinderIdBuildPostResponseBuildBinderApiV1BindersBinderIdBuildPost | HTTPValidationError
    """

    return sync_detailed(
        binder_id=binder_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    binder_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    BuildBinderApiV1BindersBinderIdBuildPostResponseBuildBinderApiV1BindersBinderIdBuildPost
    | HTTPValidationError
]:
    """Build Binder

    Args:
        binder_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[BuildBinderApiV1BindersBinderIdBuildPostResponseBuildBinderApiV1BindersBinderIdBuildPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        binder_id=binder_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    binder_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    BuildBinderApiV1BindersBinderIdBuildPostResponseBuildBinderApiV1BindersBinderIdBuildPost
    | HTTPValidationError
    | None
):
    """Build Binder

    Args:
        binder_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        BuildBinderApiV1BindersBinderIdBuildPostResponseBuildBinderApiV1BindersBinderIdBuildPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            binder_id=binder_id,
            client=client,
        )
    ).parsed
