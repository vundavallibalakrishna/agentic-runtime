from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.accept_risk_api_v1_ext_grc_risks_risk_id_accept_post_body import (
    AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostBody,
)
from ...models.accept_risk_api_v1_ext_grc_risks_risk_id_accept_post_response_accept_risk_api_v1_ext_grc_risks_risk_id_accept_post import (
    AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostResponseAcceptRiskApiV1ExtGrcRisksRiskIdAcceptPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    risk_id: UUID,
    *,
    body: AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/risks/{risk_id}:accept".format(
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
    AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostResponseAcceptRiskApiV1ExtGrcRisksRiskIdAcceptPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostResponseAcceptRiskApiV1ExtGrcRisksRiskIdAcceptPost.from_dict(
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
    AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostResponseAcceptRiskApiV1ExtGrcRisksRiskIdAcceptPost
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
    body: AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostBody,
) -> Response[
    AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostResponseAcceptRiskApiV1ExtGrcRisksRiskIdAcceptPost
    | HTTPValidationError
]:
    """Accept Risk

    Args:
        risk_id (UUID):
        body (AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostResponseAcceptRiskApiV1ExtGrcRisksRiskIdAcceptPost | HTTPValidationError]
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
    body: AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostBody,
) -> (
    AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostResponseAcceptRiskApiV1ExtGrcRisksRiskIdAcceptPost
    | HTTPValidationError
    | None
):
    """Accept Risk

    Args:
        risk_id (UUID):
        body (AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostResponseAcceptRiskApiV1ExtGrcRisksRiskIdAcceptPost | HTTPValidationError
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
    body: AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostBody,
) -> Response[
    AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostResponseAcceptRiskApiV1ExtGrcRisksRiskIdAcceptPost
    | HTTPValidationError
]:
    """Accept Risk

    Args:
        risk_id (UUID):
        body (AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostResponseAcceptRiskApiV1ExtGrcRisksRiskIdAcceptPost | HTTPValidationError]
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
    body: AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostBody,
) -> (
    AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostResponseAcceptRiskApiV1ExtGrcRisksRiskIdAcceptPost
    | HTTPValidationError
    | None
):
    """Accept Risk

    Args:
        risk_id (UUID):
        body (AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AcceptRiskApiV1ExtGrcRisksRiskIdAcceptPostResponseAcceptRiskApiV1ExtGrcRisksRiskIdAcceptPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            risk_id=risk_id,
            client=client,
            body=body,
        )
    ).parsed
