from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.incident_patch import IncidentPatch
from ...models.patch_incident_api_v1_ai_incidents_incident_id_patch_response_patch_incident_api_v1_ai_incidents_incident_id_patch import (
    PatchIncidentApiV1AiIncidentsIncidentIdPatchResponsePatchIncidentApiV1AiIncidentsIncidentIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    incident_id: UUID,
    *,
    body: IncidentPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/ai-incidents/{incident_id}".format(
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
    | PatchIncidentApiV1AiIncidentsIncidentIdPatchResponsePatchIncidentApiV1AiIncidentsIncidentIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchIncidentApiV1AiIncidentsIncidentIdPatchResponsePatchIncidentApiV1AiIncidentsIncidentIdPatch.from_dict(
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
    | PatchIncidentApiV1AiIncidentsIncidentIdPatchResponsePatchIncidentApiV1AiIncidentsIncidentIdPatch
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
    body: IncidentPatch,
) -> Response[
    HTTPValidationError
    | PatchIncidentApiV1AiIncidentsIncidentIdPatchResponsePatchIncidentApiV1AiIncidentsIncidentIdPatch
]:
    """Patch Incident

    Args:
        incident_id (UUID):
        body (IncidentPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchIncidentApiV1AiIncidentsIncidentIdPatchResponsePatchIncidentApiV1AiIncidentsIncidentIdPatch]
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
    body: IncidentPatch,
) -> (
    HTTPValidationError
    | PatchIncidentApiV1AiIncidentsIncidentIdPatchResponsePatchIncidentApiV1AiIncidentsIncidentIdPatch
    | None
):
    """Patch Incident

    Args:
        incident_id (UUID):
        body (IncidentPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchIncidentApiV1AiIncidentsIncidentIdPatchResponsePatchIncidentApiV1AiIncidentsIncidentIdPatch
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
    body: IncidentPatch,
) -> Response[
    HTTPValidationError
    | PatchIncidentApiV1AiIncidentsIncidentIdPatchResponsePatchIncidentApiV1AiIncidentsIncidentIdPatch
]:
    """Patch Incident

    Args:
        incident_id (UUID):
        body (IncidentPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchIncidentApiV1AiIncidentsIncidentIdPatchResponsePatchIncidentApiV1AiIncidentsIncidentIdPatch]
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
    body: IncidentPatch,
) -> (
    HTTPValidationError
    | PatchIncidentApiV1AiIncidentsIncidentIdPatchResponsePatchIncidentApiV1AiIncidentsIncidentIdPatch
    | None
):
    """Patch Incident

    Args:
        incident_id (UUID):
        body (IncidentPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchIncidentApiV1AiIncidentsIncidentIdPatchResponsePatchIncidentApiV1AiIncidentsIncidentIdPatch
    """

    return (
        await asyncio_detailed(
            incident_id=incident_id,
            client=client,
            body=body,
        )
    ).parsed
