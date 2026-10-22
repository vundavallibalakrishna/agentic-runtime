from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.resume_routine_api_v1_routines_routine_id_resume_post_response_resume_routine_api_v1_routines_routine_id_resume_post import (
    ResumeRoutineApiV1RoutinesRoutineIdResumePostResponseResumeRoutineApiV1RoutinesRoutineIdResumePost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    routine_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/routines/{routine_id}:resume".format(
            routine_id=quote(str(routine_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ResumeRoutineApiV1RoutinesRoutineIdResumePostResponseResumeRoutineApiV1RoutinesRoutineIdResumePost
    | None
):
    if response.status_code == 200:
        response_200 = ResumeRoutineApiV1RoutinesRoutineIdResumePostResponseResumeRoutineApiV1RoutinesRoutineIdResumePost.from_dict(
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
    | ResumeRoutineApiV1RoutinesRoutineIdResumePostResponseResumeRoutineApiV1RoutinesRoutineIdResumePost
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
    | ResumeRoutineApiV1RoutinesRoutineIdResumePostResponseResumeRoutineApiV1RoutinesRoutineIdResumePost
]:
    """Resume Routine

    Args:
        routine_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ResumeRoutineApiV1RoutinesRoutineIdResumePostResponseResumeRoutineApiV1RoutinesRoutineIdResumePost]
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
    | ResumeRoutineApiV1RoutinesRoutineIdResumePostResponseResumeRoutineApiV1RoutinesRoutineIdResumePost
    | None
):
    """Resume Routine

    Args:
        routine_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ResumeRoutineApiV1RoutinesRoutineIdResumePostResponseResumeRoutineApiV1RoutinesRoutineIdResumePost
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
    | ResumeRoutineApiV1RoutinesRoutineIdResumePostResponseResumeRoutineApiV1RoutinesRoutineIdResumePost
]:
    """Resume Routine

    Args:
        routine_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ResumeRoutineApiV1RoutinesRoutineIdResumePostResponseResumeRoutineApiV1RoutinesRoutineIdResumePost]
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
    | ResumeRoutineApiV1RoutinesRoutineIdResumePostResponseResumeRoutineApiV1RoutinesRoutineIdResumePost
    | None
):
    """Resume Routine

    Args:
        routine_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ResumeRoutineApiV1RoutinesRoutineIdResumePostResponseResumeRoutineApiV1RoutinesRoutineIdResumePost
    """

    return (
        await asyncio_detailed(
            routine_id=routine_id,
            client=client,
        )
    ).parsed
