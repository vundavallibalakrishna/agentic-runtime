from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_events_api_v1_routines_routine_id_events_get_response_list_events_api_v1_routines_routine_id_events_get import (
    ListEventsApiV1RoutinesRoutineIdEventsGetResponseListEventsApiV1RoutinesRoutineIdEventsGet,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    routine_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/routines/{routine_id}/events".format(
            routine_id=quote(str(routine_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListEventsApiV1RoutinesRoutineIdEventsGetResponseListEventsApiV1RoutinesRoutineIdEventsGet
    | None
):
    if response.status_code == 200:
        response_200 = ListEventsApiV1RoutinesRoutineIdEventsGetResponseListEventsApiV1RoutinesRoutineIdEventsGet.from_dict(
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
    | ListEventsApiV1RoutinesRoutineIdEventsGetResponseListEventsApiV1RoutinesRoutineIdEventsGet
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    routine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | ListEventsApiV1RoutinesRoutineIdEventsGetResponseListEventsApiV1RoutinesRoutineIdEventsGet
]:
    """List Events

    Args:
        routine_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListEventsApiV1RoutinesRoutineIdEventsGetResponseListEventsApiV1RoutinesRoutineIdEventsGet]
    """

    kwargs = _get_kwargs(
        routine_id=routine_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    routine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | ListEventsApiV1RoutinesRoutineIdEventsGetResponseListEventsApiV1RoutinesRoutineIdEventsGet
    | None
):
    """List Events

    Args:
        routine_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListEventsApiV1RoutinesRoutineIdEventsGetResponseListEventsApiV1RoutinesRoutineIdEventsGet
    """

    return sync_detailed(
        routine_id=routine_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    routine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | ListEventsApiV1RoutinesRoutineIdEventsGetResponseListEventsApiV1RoutinesRoutineIdEventsGet
]:
    """List Events

    Args:
        routine_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListEventsApiV1RoutinesRoutineIdEventsGetResponseListEventsApiV1RoutinesRoutineIdEventsGet]
    """

    kwargs = _get_kwargs(
        routine_id=routine_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    routine_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | ListEventsApiV1RoutinesRoutineIdEventsGetResponseListEventsApiV1RoutinesRoutineIdEventsGet
    | None
):
    """List Events

    Args:
        routine_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListEventsApiV1RoutinesRoutineIdEventsGetResponseListEventsApiV1RoutinesRoutineIdEventsGet
    """

    return (
        await asyncio_detailed(
            routine_id=routine_id,
            client=client,
        )
    ).parsed
