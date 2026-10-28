from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.verify_evidence_api_v1_evidence_evidence_item_id_verify_post_response_verify_evidence_api_v1_evidence_evidence_item_id_verify_post import (
    VerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPostResponseVerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    evidence_item_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/evidence/{evidence_item_id}:verify".format(
            evidence_item_id=quote(str(evidence_item_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | VerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPostResponseVerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPost
    | None
):
    if response.status_code == 200:
        response_200 = VerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPostResponseVerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPost.from_dict(
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
    | VerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPostResponseVerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPost
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
    HTTPValidationError
    | VerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPostResponseVerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPost
]:
    """Verify Evidence

    Args:
        evidence_item_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | VerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPostResponseVerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPost]
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
    HTTPValidationError
    | VerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPostResponseVerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPost
    | None
):
    """Verify Evidence

    Args:
        evidence_item_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | VerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPostResponseVerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPost
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
    HTTPValidationError
    | VerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPostResponseVerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPost
]:
    """Verify Evidence

    Args:
        evidence_item_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | VerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPostResponseVerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPost]
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
    HTTPValidationError
    | VerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPostResponseVerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPost
    | None
):
    """Verify Evidence

    Args:
        evidence_item_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | VerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPostResponseVerifyEvidenceApiV1EvidenceEvidenceItemIdVerifyPost
    """

    return (
        await asyncio_detailed(
            evidence_item_id=evidence_item_id,
            client=client,
        )
    ).parsed
