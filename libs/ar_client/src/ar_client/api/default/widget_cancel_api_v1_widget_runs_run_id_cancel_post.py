from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.widget_cancel_api_v1_widget_runs_run_id_cancel_post_response_widget_cancel_api_v1_widget_runs_run_id_cancel_post import (
    WidgetCancelApiV1WidgetRunsRunIdCancelPostResponseWidgetCancelApiV1WidgetRunsRunIdCancelPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    run_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/widget/runs/{run_id}:cancel".format(
            run_id=quote(str(run_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | WidgetCancelApiV1WidgetRunsRunIdCancelPostResponseWidgetCancelApiV1WidgetRunsRunIdCancelPost
    | None
):
    if response.status_code == 200:
        response_200 = WidgetCancelApiV1WidgetRunsRunIdCancelPostResponseWidgetCancelApiV1WidgetRunsRunIdCancelPost.from_dict(
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
    | WidgetCancelApiV1WidgetRunsRunIdCancelPostResponseWidgetCancelApiV1WidgetRunsRunIdCancelPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | WidgetCancelApiV1WidgetRunsRunIdCancelPostResponseWidgetCancelApiV1WidgetRunsRunIdCancelPost
]:
    """Widget Cancel

    Args:
        run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | WidgetCancelApiV1WidgetRunsRunIdCancelPostResponseWidgetCancelApiV1WidgetRunsRunIdCancelPost]
    """

    kwargs = _get_kwargs(
        run_id=run_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | WidgetCancelApiV1WidgetRunsRunIdCancelPostResponseWidgetCancelApiV1WidgetRunsRunIdCancelPost
    | None
):
    """Widget Cancel

    Args:
        run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | WidgetCancelApiV1WidgetRunsRunIdCancelPostResponseWidgetCancelApiV1WidgetRunsRunIdCancelPost
    """

    return sync_detailed(
        run_id=run_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | WidgetCancelApiV1WidgetRunsRunIdCancelPostResponseWidgetCancelApiV1WidgetRunsRunIdCancelPost
]:
    """Widget Cancel

    Args:
        run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | WidgetCancelApiV1WidgetRunsRunIdCancelPostResponseWidgetCancelApiV1WidgetRunsRunIdCancelPost]
    """

    kwargs = _get_kwargs(
        run_id=run_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | WidgetCancelApiV1WidgetRunsRunIdCancelPostResponseWidgetCancelApiV1WidgetRunsRunIdCancelPost
    | None
):
    """Widget Cancel

    Args:
        run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | WidgetCancelApiV1WidgetRunsRunIdCancelPostResponseWidgetCancelApiV1WidgetRunsRunIdCancelPost
    """

    return (
        await asyncio_detailed(
            run_id=run_id,
            client=client,
        )
    ).parsed
