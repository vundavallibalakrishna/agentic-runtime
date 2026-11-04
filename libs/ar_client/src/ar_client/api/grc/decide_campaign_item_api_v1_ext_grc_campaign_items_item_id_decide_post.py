from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.decide_campaign_item_api_v1_ext_grc_campaign_items_item_id_decide_post_body import (
    DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostBody,
)
from ...models.decide_campaign_item_api_v1_ext_grc_campaign_items_item_id_decide_post_response_decide_campaign_item_api_v1_ext_grc_campaign_items_item_id_decide_post import (
    DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostResponseDecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    item_id: UUID,
    *,
    body: DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/campaign-items/{item_id}:decide".format(
            item_id=quote(str(item_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostResponseDecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostResponseDecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePost.from_dict(
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
    DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostResponseDecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostBody,
) -> Response[
    DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostResponseDecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePost
    | HTTPValidationError
]:
    """Decide Campaign Item

    Args:
        item_id (UUID):
        body (DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostResponseDecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        item_id=item_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostBody,
) -> (
    DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostResponseDecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePost
    | HTTPValidationError
    | None
):
    """Decide Campaign Item

    Args:
        item_id (UUID):
        body (DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostResponseDecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePost | HTTPValidationError
    """

    return sync_detailed(
        item_id=item_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostBody,
) -> Response[
    DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostResponseDecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePost
    | HTTPValidationError
]:
    """Decide Campaign Item

    Args:
        item_id (UUID):
        body (DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostResponseDecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        item_id=item_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    item_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostBody,
) -> (
    DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostResponseDecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePost
    | HTTPValidationError
    | None
):
    """Decide Campaign Item

    Args:
        item_id (UUID):
        body (DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePostResponseDecideCampaignItemApiV1ExtGrcCampaignItemsItemIdDecidePost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            item_id=item_id,
            client=client,
            body=body,
        )
    ).parsed
