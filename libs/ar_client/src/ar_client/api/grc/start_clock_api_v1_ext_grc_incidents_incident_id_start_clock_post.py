from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.start_clock_api_v1_ext_grc_incidents_incident_id_start_clock_post_body import (
    StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostBody,
)
from ...models.start_clock_api_v1_ext_grc_incidents_incident_id_start_clock_post_response_start_clock_api_v1_ext_grc_incidents_incident_id_start_clock_post import (
    StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostResponseStartClockApiV1ExtGrcIncidentsIncidentIdStartClockPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    incident_id: UUID,
    *,
    body: StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/incidents/{incident_id}:start-clock".format(
            incident_id=quote(str(incident_id), safe=""),
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
    | StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostResponseStartClockApiV1ExtGrcIncidentsIncidentIdStartClockPost
    | None
):
    if response.status_code == 200:
        response_200 = StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostResponseStartClockApiV1ExtGrcIncidentsIncidentIdStartClockPost.from_dict(
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
    | StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostResponseStartClockApiV1ExtGrcIncidentsIncidentIdStartClockPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    incident_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostBody,
) -> Response[
    HTTPValidationError
    | StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostResponseStartClockApiV1ExtGrcIncidentsIncidentIdStartClockPost
]:
    """Start Clock

    Args:
        incident_id (UUID):
        body (StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostResponseStartClockApiV1ExtGrcIncidentsIncidentIdStartClockPost]
    """

    kwargs = _get_kwargs(
        incident_id=incident_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    incident_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostBody,
) -> (
    HTTPValidationError
    | StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostResponseStartClockApiV1ExtGrcIncidentsIncidentIdStartClockPost
    | None
):
    """Start Clock

    Args:
        incident_id (UUID):
        body (StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostResponseStartClockApiV1ExtGrcIncidentsIncidentIdStartClockPost
    """

    return sync_detailed(
        incident_id=incident_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    incident_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostBody,
) -> Response[
    HTTPValidationError
    | StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostResponseStartClockApiV1ExtGrcIncidentsIncidentIdStartClockPost
]:
    """Start Clock

    Args:
        incident_id (UUID):
        body (StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostResponseStartClockApiV1ExtGrcIncidentsIncidentIdStartClockPost]
    """

    kwargs = _get_kwargs(
        incident_id=incident_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    incident_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostBody,
) -> (
    HTTPValidationError
    | StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostResponseStartClockApiV1ExtGrcIncidentsIncidentIdStartClockPost
    | None
):
    """Start Clock

    Args:
        incident_id (UUID):
        body (StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | StartClockApiV1ExtGrcIncidentsIncidentIdStartClockPostResponseStartClockApiV1ExtGrcIncidentsIncidentIdStartClockPost
    """

    return (
        await asyncio_detailed(
            incident_id=incident_id,
            client=client,
            body=body,
        )
    ).parsed
