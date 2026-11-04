from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.add_treatment_api_v1_ext_grc_risks_risk_id_treatments_post_body import (
    AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostBody,
)
from ...models.add_treatment_api_v1_ext_grc_risks_risk_id_treatments_post_response_add_treatment_api_v1_ext_grc_risks_risk_id_treatments_post import (
    AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostResponseAddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    risk_id: UUID,
    *,
    body: AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/risks/{risk_id}/treatments".format(
            risk_id=quote(str(risk_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostResponseAddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostResponseAddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPost.from_dict(
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
    AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostResponseAddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    risk_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostBody,
) -> Response[
    AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostResponseAddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPost
    | HTTPValidationError
]:
    """Add Treatment

    Args:
        risk_id (UUID):
        body (AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostResponseAddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        risk_id=risk_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    risk_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostBody,
) -> (
    AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostResponseAddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPost
    | HTTPValidationError
    | None
):
    """Add Treatment

    Args:
        risk_id (UUID):
        body (AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostResponseAddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPost | HTTPValidationError
    """

    return sync_detailed(
        risk_id=risk_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    risk_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostBody,
) -> Response[
    AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostResponseAddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPost
    | HTTPValidationError
]:
    """Add Treatment

    Args:
        risk_id (UUID):
        body (AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostResponseAddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        risk_id=risk_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    risk_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostBody,
) -> (
    AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostResponseAddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPost
    | HTTPValidationError
    | None
):
    """Add Treatment

    Args:
        risk_id (UUID):
        body (AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPostResponseAddTreatmentApiV1ExtGrcRisksRiskIdTreatmentsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            risk_id=risk_id,
            client=client,
            body=body,
        )
    ).parsed
