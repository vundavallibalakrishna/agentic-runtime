from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_constraint_api_v1_sod_constraints_constraint_id_delete_response_delete_constraint_api_v1_sod_constraints_constraint_id_delete import (
    DeleteConstraintApiV1SodConstraintsConstraintIdDeleteResponseDeleteConstraintApiV1SodConstraintsConstraintIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    constraint_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/sod-constraints/{constraint_id}".format(
            constraint_id=quote(str(constraint_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeleteConstraintApiV1SodConstraintsConstraintIdDeleteResponseDeleteConstraintApiV1SodConstraintsConstraintIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DeleteConstraintApiV1SodConstraintsConstraintIdDeleteResponseDeleteConstraintApiV1SodConstraintsConstraintIdDelete.from_dict(
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
    DeleteConstraintApiV1SodConstraintsConstraintIdDeleteResponseDeleteConstraintApiV1SodConstraintsConstraintIdDelete
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    constraint_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteConstraintApiV1SodConstraintsConstraintIdDeleteResponseDeleteConstraintApiV1SodConstraintsConstraintIdDelete
    | HTTPValidationError
]:
    """Delete Constraint

    Args:
        constraint_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteConstraintApiV1SodConstraintsConstraintIdDeleteResponseDeleteConstraintApiV1SodConstraintsConstraintIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        constraint_id=constraint_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    constraint_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteConstraintApiV1SodConstraintsConstraintIdDeleteResponseDeleteConstraintApiV1SodConstraintsConstraintIdDelete
    | HTTPValidationError
    | None
):
    """Delete Constraint

    Args:
        constraint_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteConstraintApiV1SodConstraintsConstraintIdDeleteResponseDeleteConstraintApiV1SodConstraintsConstraintIdDelete | HTTPValidationError
    """

    return sync_detailed(
        constraint_id=constraint_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    constraint_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteConstraintApiV1SodConstraintsConstraintIdDeleteResponseDeleteConstraintApiV1SodConstraintsConstraintIdDelete
    | HTTPValidationError
]:
    """Delete Constraint

    Args:
        constraint_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteConstraintApiV1SodConstraintsConstraintIdDeleteResponseDeleteConstraintApiV1SodConstraintsConstraintIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        constraint_id=constraint_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    constraint_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteConstraintApiV1SodConstraintsConstraintIdDeleteResponseDeleteConstraintApiV1SodConstraintsConstraintIdDelete
    | HTTPValidationError
    | None
):
    """Delete Constraint

    Args:
        constraint_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteConstraintApiV1SodConstraintsConstraintIdDeleteResponseDeleteConstraintApiV1SodConstraintsConstraintIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            constraint_id=constraint_id,
            client=client,
        )
    ).parsed
