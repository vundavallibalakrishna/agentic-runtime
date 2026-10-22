from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.cancel_job_api_v1_knowledge_jobs_job_id_cancel_post_response_cancel_job_api_v1_knowledge_jobs_job_id_cancel_post import (
    CancelJobApiV1KnowledgeJobsJobIdCancelPostResponseCancelJobApiV1KnowledgeJobsJobIdCancelPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    job_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/knowledge/jobs/{job_id}:cancel".format(
            job_id=quote(str(job_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CancelJobApiV1KnowledgeJobsJobIdCancelPostResponseCancelJobApiV1KnowledgeJobsJobIdCancelPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CancelJobApiV1KnowledgeJobsJobIdCancelPostResponseCancelJobApiV1KnowledgeJobsJobIdCancelPost.from_dict(
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
    CancelJobApiV1KnowledgeJobsJobIdCancelPostResponseCancelJobApiV1KnowledgeJobsJobIdCancelPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    job_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    CancelJobApiV1KnowledgeJobsJobIdCancelPostResponseCancelJobApiV1KnowledgeJobsJobIdCancelPost
    | HTTPValidationError
]:
    """Cancel Job

    Args:
        job_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CancelJobApiV1KnowledgeJobsJobIdCancelPostResponseCancelJobApiV1KnowledgeJobsJobIdCancelPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        job_id=job_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    job_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    CancelJobApiV1KnowledgeJobsJobIdCancelPostResponseCancelJobApiV1KnowledgeJobsJobIdCancelPost
    | HTTPValidationError
    | None
):
    """Cancel Job

    Args:
        job_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CancelJobApiV1KnowledgeJobsJobIdCancelPostResponseCancelJobApiV1KnowledgeJobsJobIdCancelPost | HTTPValidationError
    """

    return sync_detailed(
        job_id=job_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    job_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    CancelJobApiV1KnowledgeJobsJobIdCancelPostResponseCancelJobApiV1KnowledgeJobsJobIdCancelPost
    | HTTPValidationError
]:
    """Cancel Job

    Args:
        job_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CancelJobApiV1KnowledgeJobsJobIdCancelPostResponseCancelJobApiV1KnowledgeJobsJobIdCancelPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        job_id=job_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    job_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    CancelJobApiV1KnowledgeJobsJobIdCancelPostResponseCancelJobApiV1KnowledgeJobsJobIdCancelPost
    | HTTPValidationError
    | None
):
    """Cancel Job

    Args:
        job_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CancelJobApiV1KnowledgeJobsJobIdCancelPostResponseCancelJobApiV1KnowledgeJobsJobIdCancelPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            job_id=job_id,
            client=client,
        )
    ).parsed
