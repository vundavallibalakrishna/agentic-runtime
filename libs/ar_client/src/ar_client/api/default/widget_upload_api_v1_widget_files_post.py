from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.body_widget_upload_api_v1_widget_files_post import (
    BodyWidgetUploadApiV1WidgetFilesPost,
)
from ...models.http_validation_error import HTTPValidationError
from ...models.widget_upload_api_v1_widget_files_post_response_widget_upload_api_v1_widget_files_post import (
    WidgetUploadApiV1WidgetFilesPostResponseWidgetUploadApiV1WidgetFilesPost,
)
from typing import cast


def _get_kwargs(
    *,
    body: BodyWidgetUploadApiV1WidgetFilesPost,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/widget/files",
    }

    _kwargs["files"] = body.to_multipart()

    headers["Content-Type"] = "multipart/form-data; boundary=+++"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | WidgetUploadApiV1WidgetFilesPostResponseWidgetUploadApiV1WidgetFilesPost
    | None
):
    if response.status_code == 200:
        response_200 = (
            WidgetUploadApiV1WidgetFilesPostResponseWidgetUploadApiV1WidgetFilesPost.from_dict(
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
    HTTPValidationError | WidgetUploadApiV1WidgetFilesPostResponseWidgetUploadApiV1WidgetFilesPost
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
    body: BodyWidgetUploadApiV1WidgetFilesPost,
) -> Response[
    HTTPValidationError | WidgetUploadApiV1WidgetFilesPostResponseWidgetUploadApiV1WidgetFilesPost
]:
    """Widget Upload

     The same upload the signed-in chat uses, under the widget session.

    Args:
        body (BodyWidgetUploadApiV1WidgetFilesPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | WidgetUploadApiV1WidgetFilesPostResponseWidgetUploadApiV1WidgetFilesPost]
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
    body: BodyWidgetUploadApiV1WidgetFilesPost,
) -> (
    HTTPValidationError
    | WidgetUploadApiV1WidgetFilesPostResponseWidgetUploadApiV1WidgetFilesPost
    | None
):
    """Widget Upload

     The same upload the signed-in chat uses, under the widget session.

    Args:
        body (BodyWidgetUploadApiV1WidgetFilesPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | WidgetUploadApiV1WidgetFilesPostResponseWidgetUploadApiV1WidgetFilesPost
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: BodyWidgetUploadApiV1WidgetFilesPost,
) -> Response[
    HTTPValidationError | WidgetUploadApiV1WidgetFilesPostResponseWidgetUploadApiV1WidgetFilesPost
]:
    """Widget Upload

     The same upload the signed-in chat uses, under the widget session.

    Args:
        body (BodyWidgetUploadApiV1WidgetFilesPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | WidgetUploadApiV1WidgetFilesPostResponseWidgetUploadApiV1WidgetFilesPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: BodyWidgetUploadApiV1WidgetFilesPost,
) -> (
    HTTPValidationError
    | WidgetUploadApiV1WidgetFilesPostResponseWidgetUploadApiV1WidgetFilesPost
    | None
):
    """Widget Upload

     The same upload the signed-in chat uses, under the widget session.

    Args:
        body (BodyWidgetUploadApiV1WidgetFilesPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | WidgetUploadApiV1WidgetFilesPostResponseWidgetUploadApiV1WidgetFilesPost
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
