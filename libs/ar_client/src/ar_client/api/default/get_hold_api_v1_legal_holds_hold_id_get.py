from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_hold_api_v1_legal_holds_hold_id_get_response_get_hold_api_v1_legal_holds_hold_id_get import (
    GetHoldApiV1LegalHoldsHoldIdGetResponseGetHoldApiV1LegalHoldsHoldIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    hold_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/legal-holds/{hold_id}".format(
            hold_id=quote(str(hold_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetHoldApiV1LegalHoldsHoldIdGetResponseGetHoldApiV1LegalHoldsHoldIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = (
            GetHoldApiV1LegalHoldsHoldIdGetResponseGetHoldApiV1LegalHoldsHoldIdGet.from_dict(
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
    GetHoldApiV1LegalHoldsHoldIdGetResponseGetHoldApiV1LegalHoldsHoldIdGet | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    hold_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetHoldApiV1LegalHoldsHoldIdGetResponseGetHoldApiV1LegalHoldsHoldIdGet | HTTPValidationError
]:
    """Get Hold

    Args:
        hold_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetHoldApiV1LegalHoldsHoldIdGetResponseGetHoldApiV1LegalHoldsHoldIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        hold_id=hold_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    hold_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetHoldApiV1LegalHoldsHoldIdGetResponseGetHoldApiV1LegalHoldsHoldIdGet
    | HTTPValidationError
    | None
):
    """Get Hold

    Args:
        hold_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetHoldApiV1LegalHoldsHoldIdGetResponseGetHoldApiV1LegalHoldsHoldIdGet | HTTPValidationError
    """

    return sync_detailed(
        hold_id=hold_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    hold_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetHoldApiV1LegalHoldsHoldIdGetResponseGetHoldApiV1LegalHoldsHoldIdGet | HTTPValidationError
]:
    """Get Hold

    Args:
        hold_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetHoldApiV1LegalHoldsHoldIdGetResponseGetHoldApiV1LegalHoldsHoldIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        hold_id=hold_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    hold_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetHoldApiV1LegalHoldsHoldIdGetResponseGetHoldApiV1LegalHoldsHoldIdGet
    | HTTPValidationError
    | None
):
    """Get Hold

    Args:
        hold_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetHoldApiV1LegalHoldsHoldIdGetResponseGetHoldApiV1LegalHoldsHoldIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            hold_id=hold_id,
            client=client,
        )
    ).parsed
