from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.rotate_secret_api_v1_routines_routine_id_rotate_webhook_secret_post_response_rotate_secret_api_v1_routines_routine_id_rotate_webhook_secret_post import (
    RotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPostResponseRotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    routine_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/routines/{routine_id}:rotate-webhook-secret".format(
            routine_id=quote(str(routine_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | RotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPostResponseRotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPost
    | None
):
    if response.status_code == 200:
        response_200 = RotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPostResponseRotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPost.from_dict(
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
    | RotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPostResponseRotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPost
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
    | RotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPostResponseRotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPost
]:
    """Rotate Secret

    Args:
        routine_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPostResponseRotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPost]
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
    | RotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPostResponseRotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPost
    | None
):
    """Rotate Secret

    Args:
        routine_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPostResponseRotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPost
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
    | RotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPostResponseRotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPost
]:
    """Rotate Secret

    Args:
        routine_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPostResponseRotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPost]
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
    | RotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPostResponseRotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPost
    | None
):
    """Rotate Secret

    Args:
        routine_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPostResponseRotateSecretApiV1RoutinesRoutineIdRotateWebhookSecretPost
    """

    return (
        await asyncio_detailed(
            routine_id=routine_id,
            client=client,
        )
    ).parsed
