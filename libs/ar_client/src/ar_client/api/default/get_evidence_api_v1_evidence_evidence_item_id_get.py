from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_evidence_api_v1_evidence_evidence_item_id_get_response_get_evidence_api_v1_evidence_evidence_item_id_get import (
    GetEvidenceApiV1EvidenceEvidenceItemIdGetResponseGetEvidenceApiV1EvidenceEvidenceItemIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    evidence_item_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/evidence/{evidence_item_id}".format(
            evidence_item_id=quote(str(evidence_item_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetEvidenceApiV1EvidenceEvidenceItemIdGetResponseGetEvidenceApiV1EvidenceEvidenceItemIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetEvidenceApiV1EvidenceEvidenceItemIdGetResponseGetEvidenceApiV1EvidenceEvidenceItemIdGet.from_dict(
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
    GetEvidenceApiV1EvidenceEvidenceItemIdGetResponseGetEvidenceApiV1EvidenceEvidenceItemIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    evidence_item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetEvidenceApiV1EvidenceEvidenceItemIdGetResponseGetEvidenceApiV1EvidenceEvidenceItemIdGet
    | HTTPValidationError
]:
    """Get Evidence

    Args:
        evidence_item_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetEvidenceApiV1EvidenceEvidenceItemIdGetResponseGetEvidenceApiV1EvidenceEvidenceItemIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        evidence_item_id=evidence_item_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    evidence_item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetEvidenceApiV1EvidenceEvidenceItemIdGetResponseGetEvidenceApiV1EvidenceEvidenceItemIdGet
    | HTTPValidationError
    | None
):
    """Get Evidence

    Args:
        evidence_item_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetEvidenceApiV1EvidenceEvidenceItemIdGetResponseGetEvidenceApiV1EvidenceEvidenceItemIdGet | HTTPValidationError
    """

    return sync_detailed(
        evidence_item_id=evidence_item_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    evidence_item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetEvidenceApiV1EvidenceEvidenceItemIdGetResponseGetEvidenceApiV1EvidenceEvidenceItemIdGet
    | HTTPValidationError
]:
    """Get Evidence

    Args:
        evidence_item_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetEvidenceApiV1EvidenceEvidenceItemIdGetResponseGetEvidenceApiV1EvidenceEvidenceItemIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        evidence_item_id=evidence_item_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    evidence_item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetEvidenceApiV1EvidenceEvidenceItemIdGetResponseGetEvidenceApiV1EvidenceEvidenceItemIdGet
    | HTTPValidationError
    | None
):
    """Get Evidence

    Args:
        evidence_item_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetEvidenceApiV1EvidenceEvidenceItemIdGetResponseGetEvidenceApiV1EvidenceEvidenceItemIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            evidence_item_id=evidence_item_id,
            client=client,
        )
    ).parsed
