from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_source_api_v1_knowledge_sources_source_id_delete_response_delete_source_api_v1_knowledge_sources_source_id_delete import (
    DeleteSourceApiV1KnowledgeSourcesSourceIdDeleteResponseDeleteSourceApiV1KnowledgeSourcesSourceIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    source_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/knowledge/sources/{source_id}".format(
            source_id=quote(str(source_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeleteSourceApiV1KnowledgeSourcesSourceIdDeleteResponseDeleteSourceApiV1KnowledgeSourcesSourceIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 202:
        response_202 = DeleteSourceApiV1KnowledgeSourcesSourceIdDeleteResponseDeleteSourceApiV1KnowledgeSourcesSourceIdDelete.from_dict(
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
    DeleteSourceApiV1KnowledgeSourcesSourceIdDeleteResponseDeleteSourceApiV1KnowledgeSourcesSourceIdDelete
    | HTTPValidationError
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
    DeleteSourceApiV1KnowledgeSourcesSourceIdDeleteResponseDeleteSourceApiV1KnowledgeSourcesSourceIdDelete
    | HTTPValidationError
]:
    """Delete Source

    Args:
        source_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteSourceApiV1KnowledgeSourcesSourceIdDeleteResponseDeleteSourceApiV1KnowledgeSourcesSourceIdDelete | HTTPValidationError]
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
    DeleteSourceApiV1KnowledgeSourcesSourceIdDeleteResponseDeleteSourceApiV1KnowledgeSourcesSourceIdDelete
    | HTTPValidationError
    | None
):
    """Delete Source

    Args:
        source_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteSourceApiV1KnowledgeSourcesSourceIdDeleteResponseDeleteSourceApiV1KnowledgeSourcesSourceIdDelete | HTTPValidationError
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
    DeleteSourceApiV1KnowledgeSourcesSourceIdDeleteResponseDeleteSourceApiV1KnowledgeSourcesSourceIdDelete
    | HTTPValidationError
]:
    """Delete Source

    Args:
        source_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteSourceApiV1KnowledgeSourcesSourceIdDeleteResponseDeleteSourceApiV1KnowledgeSourcesSourceIdDelete | HTTPValidationError]
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
    DeleteSourceApiV1KnowledgeSourcesSourceIdDeleteResponseDeleteSourceApiV1KnowledgeSourcesSourceIdDelete
    | HTTPValidationError
    | None
):
    """Delete Source

    Args:
        source_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteSourceApiV1KnowledgeSourcesSourceIdDeleteResponseDeleteSourceApiV1KnowledgeSourcesSourceIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            source_id=source_id,
            client=client,
        )
    ).parsed
