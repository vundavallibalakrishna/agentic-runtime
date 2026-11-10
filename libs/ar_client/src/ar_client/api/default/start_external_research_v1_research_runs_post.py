from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.research_body import ResearchBody
from ...models.start_external_research_v1_research_runs_post_response_start_external_research_v1_research_runs_post import (
    StartExternalResearchV1ResearchRunsPostResponseStartExternalResearchV1ResearchRunsPost,
)
from typing import cast


def _get_kwargs(
    *,
    body: ResearchBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/research/runs",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | StartExternalResearchV1ResearchRunsPostResponseStartExternalResearchV1ResearchRunsPost
    | None
):
    if response.status_code == 202:
        response_202 = StartExternalResearchV1ResearchRunsPostResponseStartExternalResearchV1ResearchRunsPost.from_dict(
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
    | StartExternalResearchV1ResearchRunsPostResponseStartExternalResearchV1ResearchRunsPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ResearchBody,
) -> Response[
    HTTPValidationError
    | StartExternalResearchV1ResearchRunsPostResponseStartExternalResearchV1ResearchRunsPost
]:
    """Start External Research

     Start research with an agent API key. The same run streams on the session API.

    Args:
        body (ResearchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | StartExternalResearchV1ResearchRunsPostResponseStartExternalResearchV1ResearchRunsPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: ResearchBody,
) -> (
    HTTPValidationError
    | StartExternalResearchV1ResearchRunsPostResponseStartExternalResearchV1ResearchRunsPost
    | None
):
    """Start External Research

     Start research with an agent API key. The same run streams on the session API.

    Args:
        body (ResearchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | StartExternalResearchV1ResearchRunsPostResponseStartExternalResearchV1ResearchRunsPost
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ResearchBody,
) -> Response[
    HTTPValidationError
    | StartExternalResearchV1ResearchRunsPostResponseStartExternalResearchV1ResearchRunsPost
]:
    """Start External Research

     Start research with an agent API key. The same run streams on the session API.

    Args:
        body (ResearchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | StartExternalResearchV1ResearchRunsPostResponseStartExternalResearchV1ResearchRunsPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: ResearchBody,
) -> (
    HTTPValidationError
    | StartExternalResearchV1ResearchRunsPostResponseStartExternalResearchV1ResearchRunsPost
    | None
):
    """Start External Research

     Start research with an agent API key. The same run streams on the session API.

    Args:
        body (ResearchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | StartExternalResearchV1ResearchRunsPostResponseStartExternalResearchV1ResearchRunsPost
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
