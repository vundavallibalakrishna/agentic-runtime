from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_queue_api_v1_review_queues_queue_id_delete_response_delete_queue_api_v1_review_queues_queue_id_delete import (
    DeleteQueueApiV1ReviewQueuesQueueIdDeleteResponseDeleteQueueApiV1ReviewQueuesQueueIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    queue_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/review-queues/{queue_id}".format(
            queue_id=quote(str(queue_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeleteQueueApiV1ReviewQueuesQueueIdDeleteResponseDeleteQueueApiV1ReviewQueuesQueueIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DeleteQueueApiV1ReviewQueuesQueueIdDeleteResponseDeleteQueueApiV1ReviewQueuesQueueIdDelete.from_dict(
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
    DeleteQueueApiV1ReviewQueuesQueueIdDeleteResponseDeleteQueueApiV1ReviewQueuesQueueIdDelete
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    queue_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteQueueApiV1ReviewQueuesQueueIdDeleteResponseDeleteQueueApiV1ReviewQueuesQueueIdDelete
    | HTTPValidationError
]:
    """Delete Queue

    Args:
        queue_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteQueueApiV1ReviewQueuesQueueIdDeleteResponseDeleteQueueApiV1ReviewQueuesQueueIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        queue_id=queue_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    queue_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteQueueApiV1ReviewQueuesQueueIdDeleteResponseDeleteQueueApiV1ReviewQueuesQueueIdDelete
    | HTTPValidationError
    | None
):
    """Delete Queue

    Args:
        queue_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteQueueApiV1ReviewQueuesQueueIdDeleteResponseDeleteQueueApiV1ReviewQueuesQueueIdDelete | HTTPValidationError
    """

    return sync_detailed(
        queue_id=queue_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    queue_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteQueueApiV1ReviewQueuesQueueIdDeleteResponseDeleteQueueApiV1ReviewQueuesQueueIdDelete
    | HTTPValidationError
]:
    """Delete Queue

    Args:
        queue_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteQueueApiV1ReviewQueuesQueueIdDeleteResponseDeleteQueueApiV1ReviewQueuesQueueIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        queue_id=queue_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    queue_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteQueueApiV1ReviewQueuesQueueIdDeleteResponseDeleteQueueApiV1ReviewQueuesQueueIdDelete
    | HTTPValidationError
    | None
):
    """Delete Queue

    Args:
        queue_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteQueueApiV1ReviewQueuesQueueIdDeleteResponseDeleteQueueApiV1ReviewQueuesQueueIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            queue_id=queue_id,
            client=client,
        )
    ).parsed
