from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_assignment_api_v1_role_assignments_assignment_id_delete_response_delete_assignment_api_v1_role_assignments_assignment_id_delete import (
    DeleteAssignmentApiV1RoleAssignmentsAssignmentIdDeleteResponseDeleteAssignmentApiV1RoleAssignmentsAssignmentIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    assignment_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/role-assignments/{assignment_id}".format(
            assignment_id=quote(str(assignment_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeleteAssignmentApiV1RoleAssignmentsAssignmentIdDeleteResponseDeleteAssignmentApiV1RoleAssignmentsAssignmentIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DeleteAssignmentApiV1RoleAssignmentsAssignmentIdDeleteResponseDeleteAssignmentApiV1RoleAssignmentsAssignmentIdDelete.from_dict(
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
    DeleteAssignmentApiV1RoleAssignmentsAssignmentIdDeleteResponseDeleteAssignmentApiV1RoleAssignmentsAssignmentIdDelete
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    assignment_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteAssignmentApiV1RoleAssignmentsAssignmentIdDeleteResponseDeleteAssignmentApiV1RoleAssignmentsAssignmentIdDelete
    | HTTPValidationError
]:
    """Delete Assignment

    Args:
        assignment_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteAssignmentApiV1RoleAssignmentsAssignmentIdDeleteResponseDeleteAssignmentApiV1RoleAssignmentsAssignmentIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        assignment_id=assignment_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    assignment_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteAssignmentApiV1RoleAssignmentsAssignmentIdDeleteResponseDeleteAssignmentApiV1RoleAssignmentsAssignmentIdDelete
    | HTTPValidationError
    | None
):
    """Delete Assignment

    Args:
        assignment_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteAssignmentApiV1RoleAssignmentsAssignmentIdDeleteResponseDeleteAssignmentApiV1RoleAssignmentsAssignmentIdDelete | HTTPValidationError
    """

    return sync_detailed(
        assignment_id=assignment_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    assignment_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteAssignmentApiV1RoleAssignmentsAssignmentIdDeleteResponseDeleteAssignmentApiV1RoleAssignmentsAssignmentIdDelete
    | HTTPValidationError
]:
    """Delete Assignment

    Args:
        assignment_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteAssignmentApiV1RoleAssignmentsAssignmentIdDeleteResponseDeleteAssignmentApiV1RoleAssignmentsAssignmentIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        assignment_id=assignment_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    assignment_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteAssignmentApiV1RoleAssignmentsAssignmentIdDeleteResponseDeleteAssignmentApiV1RoleAssignmentsAssignmentIdDelete
    | HTTPValidationError
    | None
):
    """Delete Assignment

    Args:
        assignment_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteAssignmentApiV1RoleAssignmentsAssignmentIdDeleteResponseDeleteAssignmentApiV1RoleAssignmentsAssignmentIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            assignment_id=assignment_id,
            client=client,
        )
    ).parsed
