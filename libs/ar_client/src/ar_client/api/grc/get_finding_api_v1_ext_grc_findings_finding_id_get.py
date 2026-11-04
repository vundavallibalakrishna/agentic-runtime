from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_finding_api_v1_ext_grc_findings_finding_id_get_response_get_finding_api_v1_ext_grc_findings_finding_id_get import (
    GetFindingApiV1ExtGrcFindingsFindingIdGetResponseGetFindingApiV1ExtGrcFindingsFindingIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    finding_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/findings/{finding_id}".format(
            finding_id=quote(str(finding_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetFindingApiV1ExtGrcFindingsFindingIdGetResponseGetFindingApiV1ExtGrcFindingsFindingIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetFindingApiV1ExtGrcFindingsFindingIdGetResponseGetFindingApiV1ExtGrcFindingsFindingIdGet.from_dict(
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
    GetFindingApiV1ExtGrcFindingsFindingIdGetResponseGetFindingApiV1ExtGrcFindingsFindingIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    finding_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetFindingApiV1ExtGrcFindingsFindingIdGetResponseGetFindingApiV1ExtGrcFindingsFindingIdGet
    | HTTPValidationError
]:
    """Get Finding

    Args:
        finding_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetFindingApiV1ExtGrcFindingsFindingIdGetResponseGetFindingApiV1ExtGrcFindingsFindingIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        finding_id=finding_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    finding_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetFindingApiV1ExtGrcFindingsFindingIdGetResponseGetFindingApiV1ExtGrcFindingsFindingIdGet
    | HTTPValidationError
    | None
):
    """Get Finding

    Args:
        finding_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetFindingApiV1ExtGrcFindingsFindingIdGetResponseGetFindingApiV1ExtGrcFindingsFindingIdGet | HTTPValidationError
    """

    return sync_detailed(
        finding_id=finding_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    finding_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetFindingApiV1ExtGrcFindingsFindingIdGetResponseGetFindingApiV1ExtGrcFindingsFindingIdGet
    | HTTPValidationError
]:
    """Get Finding

    Args:
        finding_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetFindingApiV1ExtGrcFindingsFindingIdGetResponseGetFindingApiV1ExtGrcFindingsFindingIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        finding_id=finding_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    finding_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetFindingApiV1ExtGrcFindingsFindingIdGetResponseGetFindingApiV1ExtGrcFindingsFindingIdGet
    | HTTPValidationError
    | None
):
    """Get Finding

    Args:
        finding_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetFindingApiV1ExtGrcFindingsFindingIdGetResponseGetFindingApiV1ExtGrcFindingsFindingIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            finding_id=finding_id,
            client=client,
        )
    ).parsed
