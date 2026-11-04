from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.body_upload_external_file_v1_agents_slug_files_post import (
    BodyUploadExternalFileV1AgentsSlugFilesPost,
)
from ...models.http_validation_error import HTTPValidationError
from ...models.upload_external_file_v1_agents_slug_files_post_response_upload_external_file_v1_agents_slug_files_post import (
    UploadExternalFileV1AgentsSlugFilesPostResponseUploadExternalFileV1AgentsSlugFilesPost,
)
from typing import cast


def _get_kwargs(
    slug: str,
    *,
    body: BodyUploadExternalFileV1AgentsSlugFilesPost,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/agents/{slug}/files".format(
            slug=quote(str(slug), safe=""),
        ),
    }

    _kwargs["files"] = body.to_multipart()

    headers["Content-Type"] = "multipart/form-data; boundary=+++"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | UploadExternalFileV1AgentsSlugFilesPostResponseUploadExternalFileV1AgentsSlugFilesPost
    | None
):
    if response.status_code == 200:
        response_200 = UploadExternalFileV1AgentsSlugFilesPostResponseUploadExternalFileV1AgentsSlugFilesPost.from_dict(
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
    | UploadExternalFileV1AgentsSlugFilesPostResponseUploadExternalFileV1AgentsSlugFilesPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    slug: str,
    *,
    client: AuthenticatedClient | Client,
    body: BodyUploadExternalFileV1AgentsSlugFilesPost,
) -> Response[
    HTTPValidationError
    | UploadExternalFileV1AgentsSlugFilesPostResponseUploadExternalFileV1AgentsSlugFilesPost
]:
    """Upload External File

    Args:
        slug (str):
        body (BodyUploadExternalFileV1AgentsSlugFilesPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UploadExternalFileV1AgentsSlugFilesPostResponseUploadExternalFileV1AgentsSlugFilesPost]
    """

    kwargs = _get_kwargs(
        slug=slug,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    slug: str,
    *,
    client: AuthenticatedClient | Client,
    body: BodyUploadExternalFileV1AgentsSlugFilesPost,
) -> (
    HTTPValidationError
    | UploadExternalFileV1AgentsSlugFilesPostResponseUploadExternalFileV1AgentsSlugFilesPost
    | None
):
    """Upload External File

    Args:
        slug (str):
        body (BodyUploadExternalFileV1AgentsSlugFilesPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UploadExternalFileV1AgentsSlugFilesPostResponseUploadExternalFileV1AgentsSlugFilesPost
    """

    return sync_detailed(
        slug=slug,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    slug: str,
    *,
    client: AuthenticatedClient | Client,
    body: BodyUploadExternalFileV1AgentsSlugFilesPost,
) -> Response[
    HTTPValidationError
    | UploadExternalFileV1AgentsSlugFilesPostResponseUploadExternalFileV1AgentsSlugFilesPost
]:
    """Upload External File

    Args:
        slug (str):
        body (BodyUploadExternalFileV1AgentsSlugFilesPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UploadExternalFileV1AgentsSlugFilesPostResponseUploadExternalFileV1AgentsSlugFilesPost]
    """

    kwargs = _get_kwargs(
        slug=slug,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    slug: str,
    *,
    client: AuthenticatedClient | Client,
    body: BodyUploadExternalFileV1AgentsSlugFilesPost,
) -> (
    HTTPValidationError
    | UploadExternalFileV1AgentsSlugFilesPostResponseUploadExternalFileV1AgentsSlugFilesPost
    | None
):
    """Upload External File

    Args:
        slug (str):
        body (BodyUploadExternalFileV1AgentsSlugFilesPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UploadExternalFileV1AgentsSlugFilesPostResponseUploadExternalFileV1AgentsSlugFilesPost
    """

    return (
        await asyncio_detailed(
            slug=slug,
            client=client,
            body=body,
        )
    ).parsed
