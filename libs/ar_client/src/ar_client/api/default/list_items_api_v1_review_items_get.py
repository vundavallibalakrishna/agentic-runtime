from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_items_api_v1_review_items_get_response_list_items_api_v1_review_items_get import (
    ListItemsApiV1ReviewItemsGetResponseListItemsApiV1ReviewItemsGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    *,
    scope: str | Unset = "to_decide",
    status: None | str | Unset = UNSET,
    queue_id: None | Unset | UUID = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["scope"] = scope

    json_status: None | str | Unset
    if isinstance(status, Unset):
        json_status = UNSET
    else:
        json_status = status
    params["status"] = json_status

    json_queue_id: None | str | Unset
    if isinstance(queue_id, Unset):
        json_queue_id = UNSET
    elif isinstance(queue_id, UUID):
        json_queue_id = str(queue_id)
    else:
        json_queue_id = queue_id
    params["queue_id"] = json_queue_id

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/review-items",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ListItemsApiV1ReviewItemsGetResponseListItemsApiV1ReviewItemsGet | None:
    if response.status_code == 200:
        response_200 = ListItemsApiV1ReviewItemsGetResponseListItemsApiV1ReviewItemsGet.from_dict(
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
    HTTPValidationError | ListItemsApiV1ReviewItemsGetResponseListItemsApiV1ReviewItemsGet
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    scope: str | Unset = "to_decide",
    status: None | str | Unset = UNSET,
    queue_id: None | Unset | UUID = UNSET,
) -> Response[
    HTTPValidationError | ListItemsApiV1ReviewItemsGetResponseListItemsApiV1ReviewItemsGet
]:
    """List Items

    Args:
        scope (str | Unset):  Default: 'to_decide'.
        status (None | str | Unset):
        queue_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListItemsApiV1ReviewItemsGetResponseListItemsApiV1ReviewItemsGet]
    """

    kwargs = _get_kwargs(
        scope=scope,
        status=status,
        queue_id=queue_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    scope: str | Unset = "to_decide",
    status: None | str | Unset = UNSET,
    queue_id: None | Unset | UUID = UNSET,
) -> HTTPValidationError | ListItemsApiV1ReviewItemsGetResponseListItemsApiV1ReviewItemsGet | None:
    """List Items

    Args:
        scope (str | Unset):  Default: 'to_decide'.
        status (None | str | Unset):
        queue_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListItemsApiV1ReviewItemsGetResponseListItemsApiV1ReviewItemsGet
    """

    return sync_detailed(
        client=client,
        scope=scope,
        status=status,
        queue_id=queue_id,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    scope: str | Unset = "to_decide",
    status: None | str | Unset = UNSET,
    queue_id: None | Unset | UUID = UNSET,
) -> Response[
    HTTPValidationError | ListItemsApiV1ReviewItemsGetResponseListItemsApiV1ReviewItemsGet
]:
    """List Items

    Args:
        scope (str | Unset):  Default: 'to_decide'.
        status (None | str | Unset):
        queue_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListItemsApiV1ReviewItemsGetResponseListItemsApiV1ReviewItemsGet]
    """

    kwargs = _get_kwargs(
        scope=scope,
        status=status,
        queue_id=queue_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    scope: str | Unset = "to_decide",
    status: None | str | Unset = UNSET,
    queue_id: None | Unset | UUID = UNSET,
) -> HTTPValidationError | ListItemsApiV1ReviewItemsGetResponseListItemsApiV1ReviewItemsGet | None:
    """List Items

    Args:
        scope (str | Unset):  Default: 'to_decide'.
        status (None | str | Unset):
        queue_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListItemsApiV1ReviewItemsGetResponseListItemsApiV1ReviewItemsGet
    """

    return (
        await asyncio_detailed(
            client=client,
            scope=scope,
            status=status,
            queue_id=queue_id,
        )
    ).parsed
