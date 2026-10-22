from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_event_api_v1_audit_events_event_id_get_response_get_event_api_v1_audit_events_event_id_get import (
    GetEventApiV1AuditEventsEventIdGetResponseGetEventApiV1AuditEventsEventIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    event_id: int,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/audit-events/{event_id}".format(
            event_id=quote(str(event_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetEventApiV1AuditEventsEventIdGetResponseGetEventApiV1AuditEventsEventIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = (
            GetEventApiV1AuditEventsEventIdGetResponseGetEventApiV1AuditEventsEventIdGet.from_dict(
                response.json()
            )
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
    GetEventApiV1AuditEventsEventIdGetResponseGetEventApiV1AuditEventsEventIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    event_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetEventApiV1AuditEventsEventIdGetResponseGetEventApiV1AuditEventsEventIdGet
    | HTTPValidationError
]:
    """Get Event

    Args:
        event_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetEventApiV1AuditEventsEventIdGetResponseGetEventApiV1AuditEventsEventIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        event_id=event_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    event_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetEventApiV1AuditEventsEventIdGetResponseGetEventApiV1AuditEventsEventIdGet
    | HTTPValidationError
    | None
):
    """Get Event

    Args:
        event_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetEventApiV1AuditEventsEventIdGetResponseGetEventApiV1AuditEventsEventIdGet | HTTPValidationError
    """

    return sync_detailed(
        event_id=event_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    event_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetEventApiV1AuditEventsEventIdGetResponseGetEventApiV1AuditEventsEventIdGet
    | HTTPValidationError
]:
    """Get Event

    Args:
        event_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetEventApiV1AuditEventsEventIdGetResponseGetEventApiV1AuditEventsEventIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        event_id=event_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    event_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetEventApiV1AuditEventsEventIdGetResponseGetEventApiV1AuditEventsEventIdGet
    | HTTPValidationError
    | None
):
    """Get Event

    Args:
        event_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetEventApiV1AuditEventsEventIdGetResponseGetEventApiV1AuditEventsEventIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            event_id=event_id,
            client=client,
        )
    ).parsed
