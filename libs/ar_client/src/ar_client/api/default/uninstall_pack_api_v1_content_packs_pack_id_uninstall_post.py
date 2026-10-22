from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.uninstall_body import UninstallBody
from ...models.uninstall_pack_api_v1_content_packs_pack_id_uninstall_post_response_uninstall_pack_api_v1_content_packs_pack_id_uninstall_post import (
    UninstallPackApiV1ContentPacksPackIdUninstallPostResponseUninstallPackApiV1ContentPacksPackIdUninstallPost,
)
from typing import cast


def _get_kwargs(
    pack_id: str,
    *,
    body: UninstallBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/content-packs/{pack_id}:uninstall".format(
            pack_id=quote(str(pack_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | UninstallPackApiV1ContentPacksPackIdUninstallPostResponseUninstallPackApiV1ContentPacksPackIdUninstallPost
    | None
):
    if response.status_code == 200:
        response_200 = UninstallPackApiV1ContentPacksPackIdUninstallPostResponseUninstallPackApiV1ContentPacksPackIdUninstallPost.from_dict(
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
    | UninstallPackApiV1ContentPacksPackIdUninstallPostResponseUninstallPackApiV1ContentPacksPackIdUninstallPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    pack_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: UninstallBody,
) -> Response[
    HTTPValidationError
    | UninstallPackApiV1ContentPacksPackIdUninstallPostResponseUninstallPackApiV1ContentPacksPackIdUninstallPost
]:
    """Uninstall Pack

    Args:
        pack_id (str):
        body (UninstallBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UninstallPackApiV1ContentPacksPackIdUninstallPostResponseUninstallPackApiV1ContentPacksPackIdUninstallPost]
    """

    kwargs = _get_kwargs(
        pack_id=pack_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    pack_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: UninstallBody,
) -> (
    HTTPValidationError
    | UninstallPackApiV1ContentPacksPackIdUninstallPostResponseUninstallPackApiV1ContentPacksPackIdUninstallPost
    | None
):
    """Uninstall Pack

    Args:
        pack_id (str):
        body (UninstallBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UninstallPackApiV1ContentPacksPackIdUninstallPostResponseUninstallPackApiV1ContentPacksPackIdUninstallPost
    """

    return sync_detailed(
        pack_id=pack_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    pack_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: UninstallBody,
) -> Response[
    HTTPValidationError
    | UninstallPackApiV1ContentPacksPackIdUninstallPostResponseUninstallPackApiV1ContentPacksPackIdUninstallPost
]:
    """Uninstall Pack

    Args:
        pack_id (str):
        body (UninstallBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UninstallPackApiV1ContentPacksPackIdUninstallPostResponseUninstallPackApiV1ContentPacksPackIdUninstallPost]
    """

    kwargs = _get_kwargs(
        pack_id=pack_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    pack_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: UninstallBody,
) -> (
    HTTPValidationError
    | UninstallPackApiV1ContentPacksPackIdUninstallPostResponseUninstallPackApiV1ContentPacksPackIdUninstallPost
    | None
):
    """Uninstall Pack

    Args:
        pack_id (str):
        body (UninstallBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UninstallPackApiV1ContentPacksPackIdUninstallPostResponseUninstallPackApiV1ContentPacksPackIdUninstallPost
    """

    return (
        await asyncio_detailed(
            pack_id=pack_id,
            client=client,
            body=body,
        )
    ).parsed
