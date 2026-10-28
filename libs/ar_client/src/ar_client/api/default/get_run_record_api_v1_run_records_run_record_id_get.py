from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_run_record_api_v1_run_records_run_record_id_get_response_get_run_record_api_v1_run_records_run_record_id_get import (
    GetRunRecordApiV1RunRecordsRunRecordIdGetResponseGetRunRecordApiV1RunRecordsRunRecordIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    run_record_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/run-records/{run_record_id}".format(
            run_record_id=quote(str(run_record_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetRunRecordApiV1RunRecordsRunRecordIdGetResponseGetRunRecordApiV1RunRecordsRunRecordIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetRunRecordApiV1RunRecordsRunRecordIdGetResponseGetRunRecordApiV1RunRecordsRunRecordIdGet.from_dict(
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
    GetRunRecordApiV1RunRecordsRunRecordIdGetResponseGetRunRecordApiV1RunRecordsRunRecordIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    run_record_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetRunRecordApiV1RunRecordsRunRecordIdGetResponseGetRunRecordApiV1RunRecordsRunRecordIdGet
    | HTTPValidationError
]:
    """Get Run Record

    Args:
        run_record_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetRunRecordApiV1RunRecordsRunRecordIdGetResponseGetRunRecordApiV1RunRecordsRunRecordIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        run_record_id=run_record_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    run_record_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetRunRecordApiV1RunRecordsRunRecordIdGetResponseGetRunRecordApiV1RunRecordsRunRecordIdGet
    | HTTPValidationError
    | None
):
    """Get Run Record

    Args:
        run_record_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetRunRecordApiV1RunRecordsRunRecordIdGetResponseGetRunRecordApiV1RunRecordsRunRecordIdGet | HTTPValidationError
    """

    return sync_detailed(
        run_record_id=run_record_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    run_record_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetRunRecordApiV1RunRecordsRunRecordIdGetResponseGetRunRecordApiV1RunRecordsRunRecordIdGet
    | HTTPValidationError
]:
    """Get Run Record

    Args:
        run_record_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetRunRecordApiV1RunRecordsRunRecordIdGetResponseGetRunRecordApiV1RunRecordsRunRecordIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        run_record_id=run_record_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    run_record_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetRunRecordApiV1RunRecordsRunRecordIdGetResponseGetRunRecordApiV1RunRecordsRunRecordIdGet
    | HTTPValidationError
    | None
):
    """Get Run Record

    Args:
        run_record_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetRunRecordApiV1RunRecordsRunRecordIdGetResponseGetRunRecordApiV1RunRecordsRunRecordIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            run_record_id=run_record_id,
            client=client,
        )
    ).parsed
