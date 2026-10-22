from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.pause_source_api_v1_knowledge_sources_source_id_pause_post_response_pause_source_api_v1_knowledge_sources_source_id_pause_post import (
    PauseSourceApiV1KnowledgeSourcesSourceIdPausePostResponsePauseSourceApiV1KnowledgeSourcesSourceIdPausePost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    source_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/knowledge/sources/{source_id}:pause".format(
            source_id=quote(str(source_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | PauseSourceApiV1KnowledgeSourcesSourceIdPausePostResponsePauseSourceApiV1KnowledgeSourcesSourceIdPausePost
    | None
):
    if response.status_code == 200:
        response_200 = PauseSourceApiV1KnowledgeSourcesSourceIdPausePostResponsePauseSourceApiV1KnowledgeSourcesSourceIdPausePost.from_dict(
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
    | PauseSourceApiV1KnowledgeSourcesSourceIdPausePostResponsePauseSourceApiV1KnowledgeSourcesSourceIdPausePost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    source_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | PauseSourceApiV1KnowledgeSourcesSourceIdPausePostResponsePauseSourceApiV1KnowledgeSourcesSourceIdPausePost
]:
    """Pause Source

    Args:
        source_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PauseSourceApiV1KnowledgeSourcesSourceIdPausePostResponsePauseSourceApiV1KnowledgeSourcesSourceIdPausePost]
    """

    kwargs = _get_kwargs(
        source_id=source_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    source_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | PauseSourceApiV1KnowledgeSourcesSourceIdPausePostResponsePauseSourceApiV1KnowledgeSourcesSourceIdPausePost
    | None
):
    """Pause Source

    Args:
        source_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PauseSourceApiV1KnowledgeSourcesSourceIdPausePostResponsePauseSourceApiV1KnowledgeSourcesSourceIdPausePost
    """

    return sync_detailed(
        source_id=source_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    source_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | PauseSourceApiV1KnowledgeSourcesSourceIdPausePostResponsePauseSourceApiV1KnowledgeSourcesSourceIdPausePost
]:
    """Pause Source

    Args:
        source_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PauseSourceApiV1KnowledgeSourcesSourceIdPausePostResponsePauseSourceApiV1KnowledgeSourcesSourceIdPausePost]
    """

    kwargs = _get_kwargs(
        source_id=source_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    source_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | PauseSourceApiV1KnowledgeSourcesSourceIdPausePostResponsePauseSourceApiV1KnowledgeSourcesSourceIdPausePost
    | None
):
    """Pause Source

    Args:
        source_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PauseSourceApiV1KnowledgeSourcesSourceIdPausePostResponsePauseSourceApiV1KnowledgeSourcesSourceIdPausePost
    """

    return (
        await asyncio_detailed(
            source_id=source_id,
            client=client,
        )
    ).parsed
