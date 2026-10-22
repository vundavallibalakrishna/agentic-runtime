from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.upgrade_body import UpgradeBody
from ...models.upgrade_pack_api_v1_content_packs_pack_id_upgrade_post_response_upgrade_pack_api_v1_content_packs_pack_id_upgrade_post import (
    UpgradePackApiV1ContentPacksPackIdUpgradePostResponseUpgradePackApiV1ContentPacksPackIdUpgradePost,
)
from ...types import Response


def _get_kwargs(
    pack_id: str,
    *,
    body: UpgradeBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/content-packs/{pack_id}:upgrade".format(
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
    | UpgradePackApiV1ContentPacksPackIdUpgradePostResponseUpgradePackApiV1ContentPacksPackIdUpgradePost
    | None
):
    if response.status_code == 200:
        response_200 = UpgradePackApiV1ContentPacksPackIdUpgradePostResponseUpgradePackApiV1ContentPacksPackIdUpgradePost.from_dict(
            response.json()
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
    | UpgradePackApiV1ContentPacksPackIdUpgradePostResponseUpgradePackApiV1ContentPacksPackIdUpgradePost
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
    body: UpgradeBody,
) -> Response[
    HTTPValidationError
    | UpgradePackApiV1ContentPacksPackIdUpgradePostResponseUpgradePackApiV1ContentPacksPackIdUpgradePost
]:
    """Upgrade Pack

    Args:
        pack_id (str):
        body (UpgradeBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UpgradePackApiV1ContentPacksPackIdUpgradePostResponseUpgradePackApiV1ContentPacksPackIdUpgradePost]
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
    body: UpgradeBody,
) -> (
    HTTPValidationError
    | UpgradePackApiV1ContentPacksPackIdUpgradePostResponseUpgradePackApiV1ContentPacksPackIdUpgradePost
    | None
):
    """Upgrade Pack

    Args:
        pack_id (str):
        body (UpgradeBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UpgradePackApiV1ContentPacksPackIdUpgradePostResponseUpgradePackApiV1ContentPacksPackIdUpgradePost
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
    body: UpgradeBody,
) -> Response[
    HTTPValidationError
    | UpgradePackApiV1ContentPacksPackIdUpgradePostResponseUpgradePackApiV1ContentPacksPackIdUpgradePost
]:
    """Upgrade Pack

    Args:
        pack_id (str):
        body (UpgradeBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UpgradePackApiV1ContentPacksPackIdUpgradePostResponseUpgradePackApiV1ContentPacksPackIdUpgradePost]
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
    body: UpgradeBody,
) -> (
    HTTPValidationError
    | UpgradePackApiV1ContentPacksPackIdUpgradePostResponseUpgradePackApiV1ContentPacksPackIdUpgradePost
    | None
):
    """Upgrade Pack

    Args:
        pack_id (str):
        body (UpgradeBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UpgradePackApiV1ContentPacksPackIdUpgradePostResponseUpgradePackApiV1ContentPacksPackIdUpgradePost
    """

    return (
        await asyncio_detailed(
            pack_id=pack_id,
            client=client,
            body=body,
        )
    ).parsed
