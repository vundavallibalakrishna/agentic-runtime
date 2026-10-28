from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.file_notification_api_v1_ext_grc_incidents_incident_id_file_notification_post_body import (
    FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostBody,
)
from ...models.file_notification_api_v1_ext_grc_incidents_incident_id_file_notification_post_response_file_notification_api_v1_ext_grc_incidents_incident_id_file_notification_post import (
    FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostResponseFileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    incident_id: UUID,
    *,
    body: FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/incidents/{incident_id}:file-notification".format(
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
    FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostResponseFileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostResponseFileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPost.from_dict(
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
    FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostResponseFileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPost
    | HTTPValidationError
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
    body: FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostBody,
) -> Response[
    FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostResponseFileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPost
    | HTTPValidationError
]:
    """File Notification

    Args:
        incident_id (UUID):
        body (FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostResponseFileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPost | HTTPValidationError]
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
    body: FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostBody,
) -> (
    FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostResponseFileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPost
    | HTTPValidationError
    | None
):
    """File Notification

    Args:
        incident_id (UUID):
        body (FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostResponseFileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPost | HTTPValidationError
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
    body: FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostBody,
) -> Response[
    FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostResponseFileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPost
    | HTTPValidationError
]:
    """File Notification

    Args:
        incident_id (UUID):
        body (FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostResponseFileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPost | HTTPValidationError]
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
    body: FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostBody,
) -> (
    FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostResponseFileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPost
    | HTTPValidationError
    | None
):
    """File Notification

    Args:
        incident_id (UUID):
        body (FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        FileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPostResponseFileNotificationApiV1ExtGrcIncidentsIncidentIdFileNotificationPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            incident_id=incident_id,
            client=client,
            body=body,
        )
    ).parsed
