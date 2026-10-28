from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.put_schedule_api_v1_retention_schedules_record_class_put_response_put_schedule_api_v1_retention_schedules_record_class_put import (
    PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut,
)
from ...models.schedule_body import ScheduleBody
from typing import cast


def _get_kwargs(
    record_class: str,
    *,
    body: ScheduleBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/api/v1/retention-schedules/{record_class}".format(
            record_class=quote(str(record_class), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut
    | None
):
    if response.status_code == 200:
        response_200 = PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut.from_dict(
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
    | PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    record_class: str,
    *,
    client: AuthenticatedClient | Client,
    body: ScheduleBody,
) -> Response[
    HTTPValidationError
    | PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut
]:
    """Put Schedule

    Args:
        record_class (str):
        body (ScheduleBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut]
    """

    kwargs = _get_kwargs(
        record_class=record_class,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    record_class: str,
    *,
    client: AuthenticatedClient | Client,
    body: ScheduleBody,
) -> (
    HTTPValidationError
    | PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut
    | None
):
    """Put Schedule

    Args:
        record_class (str):
        body (ScheduleBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut
    """

    return sync_detailed(
        record_class=record_class,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    record_class: str,
    *,
    client: AuthenticatedClient | Client,
    body: ScheduleBody,
) -> Response[
    HTTPValidationError
    | PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut
]:
    """Put Schedule

    Args:
        record_class (str):
        body (ScheduleBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut]
    """

    kwargs = _get_kwargs(
        record_class=record_class,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    record_class: str,
    *,
    client: AuthenticatedClient | Client,
    body: ScheduleBody,
) -> (
    HTTPValidationError
    | PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut
    | None
):
    """Put Schedule

    Args:
        record_class (str):
        body (ScheduleBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PutScheduleApiV1RetentionSchedulesRecordClassPutResponsePutScheduleApiV1RetentionSchedulesRecordClassPut
    """

    return (
        await asyncio_detailed(
            record_class=record_class,
            client=client,
            body=body,
        )
    ).parsed
