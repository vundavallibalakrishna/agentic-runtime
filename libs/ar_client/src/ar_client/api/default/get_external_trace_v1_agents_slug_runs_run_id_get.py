from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_external_trace_v1_agents_slug_runs_run_id_get_response_get_external_trace_v1_agents_slug_runs_run_id_get import (
    GetExternalTraceV1AgentsSlugRunsRunIdGetResponseGetExternalTraceV1AgentsSlugRunsRunIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    slug: str,
    run_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/agents/{slug}/runs/{run_id}".format(
            slug=quote(str(slug), safe=""),
            run_id=quote(str(run_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetExternalTraceV1AgentsSlugRunsRunIdGetResponseGetExternalTraceV1AgentsSlugRunsRunIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetExternalTraceV1AgentsSlugRunsRunIdGetResponseGetExternalTraceV1AgentsSlugRunsRunIdGet.from_dict(
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
    GetExternalTraceV1AgentsSlugRunsRunIdGetResponseGetExternalTraceV1AgentsSlugRunsRunIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    slug: str,
    run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetExternalTraceV1AgentsSlugRunsRunIdGetResponseGetExternalTraceV1AgentsSlugRunsRunIdGet
    | HTTPValidationError
]:
    """Get External Trace

    Args:
        slug (str):
        run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetExternalTraceV1AgentsSlugRunsRunIdGetResponseGetExternalTraceV1AgentsSlugRunsRunIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        slug=slug,
        run_id=run_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    slug: str,
    run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetExternalTraceV1AgentsSlugRunsRunIdGetResponseGetExternalTraceV1AgentsSlugRunsRunIdGet
    | HTTPValidationError
    | None
):
    """Get External Trace

    Args:
        slug (str):
        run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetExternalTraceV1AgentsSlugRunsRunIdGetResponseGetExternalTraceV1AgentsSlugRunsRunIdGet | HTTPValidationError
    """

    return sync_detailed(
        slug=slug,
        run_id=run_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    slug: str,
    run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetExternalTraceV1AgentsSlugRunsRunIdGetResponseGetExternalTraceV1AgentsSlugRunsRunIdGet
    | HTTPValidationError
]:
    """Get External Trace

    Args:
        slug (str):
        run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetExternalTraceV1AgentsSlugRunsRunIdGetResponseGetExternalTraceV1AgentsSlugRunsRunIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        slug=slug,
        run_id=run_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    slug: str,
    run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetExternalTraceV1AgentsSlugRunsRunIdGetResponseGetExternalTraceV1AgentsSlugRunsRunIdGet
    | HTTPValidationError
    | None
):
    """Get External Trace

    Args:
        slug (str):
        run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetExternalTraceV1AgentsSlugRunsRunIdGetResponseGetExternalTraceV1AgentsSlugRunsRunIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            slug=slug,
            run_id=run_id,
            client=client,
        )
    ).parsed
