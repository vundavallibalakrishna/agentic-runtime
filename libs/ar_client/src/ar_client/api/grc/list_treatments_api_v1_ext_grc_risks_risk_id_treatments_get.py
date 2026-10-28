from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_treatments_api_v1_ext_grc_risks_risk_id_treatments_get_response_list_treatments_api_v1_ext_grc_risks_risk_id_treatments_get import (
    ListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGetResponseListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGet,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    risk_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/risks/{risk_id}/treatments".format(
            risk_id=quote(str(risk_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGetResponseListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGet
    | None
):
    if response.status_code == 200:
        response_200 = ListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGetResponseListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGet.from_dict(
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
    | ListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGetResponseListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGet
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
) -> Response[
    HTTPValidationError
    | ListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGetResponseListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGet
]:
    """List Treatments

    Args:
        risk_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGetResponseListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGet]
    """

    kwargs = _get_kwargs(
        risk_id=risk_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    risk_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | ListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGetResponseListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGet
    | None
):
    """List Treatments

    Args:
        risk_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGetResponseListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGet
    """

    return sync_detailed(
        risk_id=risk_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    risk_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | ListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGetResponseListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGet
]:
    """List Treatments

    Args:
        risk_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGetResponseListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGet]
    """

    kwargs = _get_kwargs(
        risk_id=risk_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    risk_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | ListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGetResponseListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGet
    | None
):
    """List Treatments

    Args:
        risk_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGetResponseListTreatmentsApiV1ExtGrcRisksRiskIdTreatmentsGet
    """

    return (
        await asyncio_detailed(
            risk_id=risk_id,
            client=client,
        )
    ).parsed
