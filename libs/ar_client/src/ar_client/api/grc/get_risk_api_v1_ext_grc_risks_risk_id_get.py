from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_risk_api_v1_ext_grc_risks_risk_id_get_response_get_risk_api_v1_ext_grc_risks_risk_id_get import (
    GetRiskApiV1ExtGrcRisksRiskIdGetResponseGetRiskApiV1ExtGrcRisksRiskIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    risk_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/risks/{risk_id}".format(
            risk_id=quote(str(risk_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetRiskApiV1ExtGrcRisksRiskIdGetResponseGetRiskApiV1ExtGrcRisksRiskIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = (
            GetRiskApiV1ExtGrcRisksRiskIdGetResponseGetRiskApiV1ExtGrcRisksRiskIdGet.from_dict(
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
    GetRiskApiV1ExtGrcRisksRiskIdGetResponseGetRiskApiV1ExtGrcRisksRiskIdGet | HTTPValidationError
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
    GetRiskApiV1ExtGrcRisksRiskIdGetResponseGetRiskApiV1ExtGrcRisksRiskIdGet | HTTPValidationError
]:
    """Get Risk

    Args:
        risk_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetRiskApiV1ExtGrcRisksRiskIdGetResponseGetRiskApiV1ExtGrcRisksRiskIdGet | HTTPValidationError]
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
    GetRiskApiV1ExtGrcRisksRiskIdGetResponseGetRiskApiV1ExtGrcRisksRiskIdGet
    | HTTPValidationError
    | None
):
    """Get Risk

    Args:
        risk_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetRiskApiV1ExtGrcRisksRiskIdGetResponseGetRiskApiV1ExtGrcRisksRiskIdGet | HTTPValidationError
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
    GetRiskApiV1ExtGrcRisksRiskIdGetResponseGetRiskApiV1ExtGrcRisksRiskIdGet | HTTPValidationError
]:
    """Get Risk

    Args:
        risk_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetRiskApiV1ExtGrcRisksRiskIdGetResponseGetRiskApiV1ExtGrcRisksRiskIdGet | HTTPValidationError]
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
    GetRiskApiV1ExtGrcRisksRiskIdGetResponseGetRiskApiV1ExtGrcRisksRiskIdGet
    | HTTPValidationError
    | None
):
    """Get Risk

    Args:
        risk_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetRiskApiV1ExtGrcRisksRiskIdGetResponseGetRiskApiV1ExtGrcRisksRiskIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            risk_id=risk_id,
            client=client,
        )
    ).parsed
