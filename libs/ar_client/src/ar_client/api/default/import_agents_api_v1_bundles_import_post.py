from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.import_agents_api_v1_bundles_import_post_response_import_agents_api_v1_bundles_import_post import (
    ImportAgentsApiV1BundlesImportPostResponseImportAgentsApiV1BundlesImportPost,
)
from ...models.import_body import ImportBody
from ...types import Response


def _get_kwargs(
    *,
    body: ImportBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/bundles:import",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ImportAgentsApiV1BundlesImportPostResponseImportAgentsApiV1BundlesImportPost
    | None
):
    if response.status_code == 200:
        response_200 = (
            ImportAgentsApiV1BundlesImportPostResponseImportAgentsApiV1BundlesImportPost.from_dict(
                response.json()
            )
        )

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    HTTPValidationError
    | ImportAgentsApiV1BundlesImportPostResponseImportAgentsApiV1BundlesImportPost
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
    body: ImportBody,
) -> Response[
    HTTPValidationError
    | ImportAgentsApiV1BundlesImportPostResponseImportAgentsApiV1BundlesImportPost
]:
    """Import Agents

    Args:
        body (ImportBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ImportAgentsApiV1BundlesImportPostResponseImportAgentsApiV1BundlesImportPost]
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
    body: ImportBody,
) -> (
    HTTPValidationError
    | ImportAgentsApiV1BundlesImportPostResponseImportAgentsApiV1BundlesImportPost
    | None
):
    """Import Agents

    Args:
        body (ImportBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ImportAgentsApiV1BundlesImportPostResponseImportAgentsApiV1BundlesImportPost
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ImportBody,
) -> Response[
    HTTPValidationError
    | ImportAgentsApiV1BundlesImportPostResponseImportAgentsApiV1BundlesImportPost
]:
    """Import Agents

    Args:
        body (ImportBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ImportAgentsApiV1BundlesImportPostResponseImportAgentsApiV1BundlesImportPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: ImportBody,
) -> (
    HTTPValidationError
    | ImportAgentsApiV1BundlesImportPostResponseImportAgentsApiV1BundlesImportPost
    | None
):
    """Import Agents

    Args:
        body (ImportBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ImportAgentsApiV1BundlesImportPostResponseImportAgentsApiV1BundlesImportPost
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
