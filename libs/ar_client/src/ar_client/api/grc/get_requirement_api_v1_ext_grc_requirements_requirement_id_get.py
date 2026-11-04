from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_requirement_api_v1_ext_grc_requirements_requirement_id_get_response_get_requirement_api_v1_ext_grc_requirements_requirement_id_get import (
    GetRequirementApiV1ExtGrcRequirementsRequirementIdGetResponseGetRequirementApiV1ExtGrcRequirementsRequirementIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    requirement_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/requirements/{requirement_id}".format(
            requirement_id=quote(str(requirement_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetRequirementApiV1ExtGrcRequirementsRequirementIdGetResponseGetRequirementApiV1ExtGrcRequirementsRequirementIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetRequirementApiV1ExtGrcRequirementsRequirementIdGetResponseGetRequirementApiV1ExtGrcRequirementsRequirementIdGet.from_dict(
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
    GetRequirementApiV1ExtGrcRequirementsRequirementIdGetResponseGetRequirementApiV1ExtGrcRequirementsRequirementIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    requirement_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetRequirementApiV1ExtGrcRequirementsRequirementIdGetResponseGetRequirementApiV1ExtGrcRequirementsRequirementIdGet
    | HTTPValidationError
]:
    """Get Requirement

    Args:
        requirement_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetRequirementApiV1ExtGrcRequirementsRequirementIdGetResponseGetRequirementApiV1ExtGrcRequirementsRequirementIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        requirement_id=requirement_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    requirement_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetRequirementApiV1ExtGrcRequirementsRequirementIdGetResponseGetRequirementApiV1ExtGrcRequirementsRequirementIdGet
    | HTTPValidationError
    | None
):
    """Get Requirement

    Args:
        requirement_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetRequirementApiV1ExtGrcRequirementsRequirementIdGetResponseGetRequirementApiV1ExtGrcRequirementsRequirementIdGet | HTTPValidationError
    """

    return sync_detailed(
        requirement_id=requirement_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    requirement_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetRequirementApiV1ExtGrcRequirementsRequirementIdGetResponseGetRequirementApiV1ExtGrcRequirementsRequirementIdGet
    | HTTPValidationError
]:
    """Get Requirement

    Args:
        requirement_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetRequirementApiV1ExtGrcRequirementsRequirementIdGetResponseGetRequirementApiV1ExtGrcRequirementsRequirementIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        requirement_id=requirement_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    requirement_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetRequirementApiV1ExtGrcRequirementsRequirementIdGetResponseGetRequirementApiV1ExtGrcRequirementsRequirementIdGet
    | HTTPValidationError
    | None
):
    """Get Requirement

    Args:
        requirement_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetRequirementApiV1ExtGrcRequirementsRequirementIdGetResponseGetRequirementApiV1ExtGrcRequirementsRequirementIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            requirement_id=requirement_id,
            client=client,
        )
    ).parsed
