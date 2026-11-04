from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.run_control_test_api_v1_ext_grc_control_tests_test_id_run_post_response_run_control_test_api_v1_ext_grc_control_tests_test_id_run_post import (
    RunControlTestApiV1ExtGrcControlTestsTestIdRunPostResponseRunControlTestApiV1ExtGrcControlTestsTestIdRunPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    test_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/control-tests/{test_id}:run".format(
            test_id=quote(str(test_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | RunControlTestApiV1ExtGrcControlTestsTestIdRunPostResponseRunControlTestApiV1ExtGrcControlTestsTestIdRunPost
    | None
):
    if response.status_code == 202:
        response_202 = RunControlTestApiV1ExtGrcControlTestsTestIdRunPostResponseRunControlTestApiV1ExtGrcControlTestsTestIdRunPost.from_dict(
            response.json()
        )

        return response_202

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
    | RunControlTestApiV1ExtGrcControlTestsTestIdRunPostResponseRunControlTestApiV1ExtGrcControlTestsTestIdRunPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    test_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RunControlTestApiV1ExtGrcControlTestsTestIdRunPostResponseRunControlTestApiV1ExtGrcControlTestsTestIdRunPost
]:
    """Run Control Test

    Args:
        test_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RunControlTestApiV1ExtGrcControlTestsTestIdRunPostResponseRunControlTestApiV1ExtGrcControlTestsTestIdRunPost]
    """

    kwargs = _get_kwargs(
        test_id=test_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    test_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RunControlTestApiV1ExtGrcControlTestsTestIdRunPostResponseRunControlTestApiV1ExtGrcControlTestsTestIdRunPost
    | None
):
    """Run Control Test

    Args:
        test_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RunControlTestApiV1ExtGrcControlTestsTestIdRunPostResponseRunControlTestApiV1ExtGrcControlTestsTestIdRunPost
    """

    return sync_detailed(
        test_id=test_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    test_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RunControlTestApiV1ExtGrcControlTestsTestIdRunPostResponseRunControlTestApiV1ExtGrcControlTestsTestIdRunPost
]:
    """Run Control Test

    Args:
        test_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RunControlTestApiV1ExtGrcControlTestsTestIdRunPostResponseRunControlTestApiV1ExtGrcControlTestsTestIdRunPost]
    """

    kwargs = _get_kwargs(
        test_id=test_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    test_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RunControlTestApiV1ExtGrcControlTestsTestIdRunPostResponseRunControlTestApiV1ExtGrcControlTestsTestIdRunPost
    | None
):
    """Run Control Test

    Args:
        test_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RunControlTestApiV1ExtGrcControlTestsTestIdRunPostResponseRunControlTestApiV1ExtGrcControlTestsTestIdRunPost
    """

    return (
        await asyncio_detailed(
            test_id=test_id,
            client=client,
        )
    ).parsed
