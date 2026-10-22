from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.body_upload_file_api_v1_files_upload_post import BodyUploadFileApiV1FilesUploadPost
from ...models.http_validation_error import HTTPValidationError
from ...models.upload_file_api_v1_files_upload_post_response_upload_file_api_v1_files_upload_post import (
    UploadFileApiV1FilesUploadPostResponseUploadFileApiV1FilesUploadPost,
)
from typing import cast


def _get_kwargs(
    *,
    body: BodyUploadFileApiV1FilesUploadPost,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/files:upload",
    }

    _kwargs["files"] = body.to_multipart()

    headers["Content-Type"] = "multipart/form-data; boundary=+++"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | UploadFileApiV1FilesUploadPostResponseUploadFileApiV1FilesUploadPost
    | None
):
    if response.status_code == 200:
        response_200 = (
            UploadFileApiV1FilesUploadPostResponseUploadFileApiV1FilesUploadPost.from_dict(
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
    HTTPValidationError | UploadFileApiV1FilesUploadPostResponseUploadFileApiV1FilesUploadPost
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
    body: BodyUploadFileApiV1FilesUploadPost,
) -> Response[
    HTTPValidationError | UploadFileApiV1FilesUploadPostResponseUploadFileApiV1FilesUploadPost
]:
    """Upload File

    Args:
        body (BodyUploadFileApiV1FilesUploadPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UploadFileApiV1FilesUploadPostResponseUploadFileApiV1FilesUploadPost]
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
    body: BodyUploadFileApiV1FilesUploadPost,
) -> (
    HTTPValidationError
    | UploadFileApiV1FilesUploadPostResponseUploadFileApiV1FilesUploadPost
    | None
):
    """Upload File

    Args:
        body (BodyUploadFileApiV1FilesUploadPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UploadFileApiV1FilesUploadPostResponseUploadFileApiV1FilesUploadPost
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: BodyUploadFileApiV1FilesUploadPost,
) -> Response[
    HTTPValidationError | UploadFileApiV1FilesUploadPostResponseUploadFileApiV1FilesUploadPost
]:
    """Upload File

    Args:
        body (BodyUploadFileApiV1FilesUploadPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UploadFileApiV1FilesUploadPostResponseUploadFileApiV1FilesUploadPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: BodyUploadFileApiV1FilesUploadPost,
) -> (
    HTTPValidationError
    | UploadFileApiV1FilesUploadPostResponseUploadFileApiV1FilesUploadPost
    | None
):
    """Upload File

    Args:
        body (BodyUploadFileApiV1FilesUploadPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UploadFileApiV1FilesUploadPostResponseUploadFileApiV1FilesUploadPost
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
