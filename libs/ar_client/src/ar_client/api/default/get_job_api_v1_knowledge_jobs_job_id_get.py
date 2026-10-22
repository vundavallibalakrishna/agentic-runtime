from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_job_api_v1_knowledge_jobs_job_id_get_response_get_job_api_v1_knowledge_jobs_job_id_get import (
    GetJobApiV1KnowledgeJobsJobIdGetResponseGetJobApiV1KnowledgeJobsJobIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    job_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/knowledge/jobs/{job_id}".format(
            job_id=quote(str(job_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetJobApiV1KnowledgeJobsJobIdGetResponseGetJobApiV1KnowledgeJobsJobIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = (
            GetJobApiV1KnowledgeJobsJobIdGetResponseGetJobApiV1KnowledgeJobsJobIdGet.from_dict(
                response.json()
            )
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
    GetJobApiV1KnowledgeJobsJobIdGetResponseGetJobApiV1KnowledgeJobsJobIdGet | HTTPValidationError
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
    GetJobApiV1KnowledgeJobsJobIdGetResponseGetJobApiV1KnowledgeJobsJobIdGet | HTTPValidationError
]:
    """Get Job

    Args:
        job_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetJobApiV1KnowledgeJobsJobIdGetResponseGetJobApiV1KnowledgeJobsJobIdGet | HTTPValidationError]
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
    GetJobApiV1KnowledgeJobsJobIdGetResponseGetJobApiV1KnowledgeJobsJobIdGet
    | HTTPValidationError
    | None
):
    """Get Job

    Args:
        job_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetJobApiV1KnowledgeJobsJobIdGetResponseGetJobApiV1KnowledgeJobsJobIdGet | HTTPValidationError
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
    GetJobApiV1KnowledgeJobsJobIdGetResponseGetJobApiV1KnowledgeJobsJobIdGet | HTTPValidationError
]:
    """Get Job

    Args:
        job_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetJobApiV1KnowledgeJobsJobIdGetResponseGetJobApiV1KnowledgeJobsJobIdGet | HTTPValidationError]
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
    GetJobApiV1KnowledgeJobsJobIdGetResponseGetJobApiV1KnowledgeJobsJobIdGet
    | HTTPValidationError
    | None
):
    """Get Job

    Args:
        job_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetJobApiV1KnowledgeJobsJobIdGetResponseGetJobApiV1KnowledgeJobsJobIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            job_id=job_id,
            client=client,
        )
    ).parsed
