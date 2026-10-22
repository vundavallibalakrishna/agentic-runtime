from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.resume_source_api_v1_knowledge_sources_source_id_resume_post_response_resume_source_api_v1_knowledge_sources_source_id_resume_post import (
    ResumeSourceApiV1KnowledgeSourcesSourceIdResumePostResponseResumeSourceApiV1KnowledgeSourcesSourceIdResumePost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    source_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/knowledge/sources/{source_id}:resume".format(
            source_id=quote(str(source_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ResumeSourceApiV1KnowledgeSourcesSourceIdResumePostResponseResumeSourceApiV1KnowledgeSourcesSourceIdResumePost
    | None
):
    if response.status_code == 200:
        response_200 = ResumeSourceApiV1KnowledgeSourcesSourceIdResumePostResponseResumeSourceApiV1KnowledgeSourcesSourceIdResumePost.from_dict(
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
    | ResumeSourceApiV1KnowledgeSourcesSourceIdResumePostResponseResumeSourceApiV1KnowledgeSourcesSourceIdResumePost
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
    | ResumeSourceApiV1KnowledgeSourcesSourceIdResumePostResponseResumeSourceApiV1KnowledgeSourcesSourceIdResumePost
]:
    """Resume Source

    Args:
        source_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ResumeSourceApiV1KnowledgeSourcesSourceIdResumePostResponseResumeSourceApiV1KnowledgeSourcesSourceIdResumePost]
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
    | ResumeSourceApiV1KnowledgeSourcesSourceIdResumePostResponseResumeSourceApiV1KnowledgeSourcesSourceIdResumePost
    | None
):
    """Resume Source

    Args:
        source_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ResumeSourceApiV1KnowledgeSourcesSourceIdResumePostResponseResumeSourceApiV1KnowledgeSourcesSourceIdResumePost
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
    | ResumeSourceApiV1KnowledgeSourcesSourceIdResumePostResponseResumeSourceApiV1KnowledgeSourcesSourceIdResumePost
]:
    """Resume Source

    Args:
        source_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ResumeSourceApiV1KnowledgeSourcesSourceIdResumePostResponseResumeSourceApiV1KnowledgeSourcesSourceIdResumePost]
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
    | ResumeSourceApiV1KnowledgeSourcesSourceIdResumePostResponseResumeSourceApiV1KnowledgeSourcesSourceIdResumePost
    | None
):
    """Resume Source

    Args:
        source_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ResumeSourceApiV1KnowledgeSourcesSourceIdResumePostResponseResumeSourceApiV1KnowledgeSourcesSourceIdResumePost
    """

    return (
        await asyncio_detailed(
            source_id=source_id,
            client=client,
        )
    ).parsed
