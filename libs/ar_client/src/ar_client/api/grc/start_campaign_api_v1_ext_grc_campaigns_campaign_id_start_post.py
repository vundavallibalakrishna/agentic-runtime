from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.start_campaign_api_v1_ext_grc_campaigns_campaign_id_start_post_response_start_campaign_api_v1_ext_grc_campaigns_campaign_id_start_post import (
    StartCampaignApiV1ExtGrcCampaignsCampaignIdStartPostResponseStartCampaignApiV1ExtGrcCampaignsCampaignIdStartPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    campaign_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/campaigns/{campaign_id}:start".format(
            campaign_id=quote(str(campaign_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | StartCampaignApiV1ExtGrcCampaignsCampaignIdStartPostResponseStartCampaignApiV1ExtGrcCampaignsCampaignIdStartPost
    | None
):
    if response.status_code == 200:
        response_200 = StartCampaignApiV1ExtGrcCampaignsCampaignIdStartPostResponseStartCampaignApiV1ExtGrcCampaignsCampaignIdStartPost.from_dict(
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
    | StartCampaignApiV1ExtGrcCampaignsCampaignIdStartPostResponseStartCampaignApiV1ExtGrcCampaignsCampaignIdStartPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    campaign_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | StartCampaignApiV1ExtGrcCampaignsCampaignIdStartPostResponseStartCampaignApiV1ExtGrcCampaignsCampaignIdStartPost
]:
    """Start Campaign

    Args:
        campaign_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | StartCampaignApiV1ExtGrcCampaignsCampaignIdStartPostResponseStartCampaignApiV1ExtGrcCampaignsCampaignIdStartPost]
    """

    kwargs = _get_kwargs(
        campaign_id=campaign_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    campaign_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | StartCampaignApiV1ExtGrcCampaignsCampaignIdStartPostResponseStartCampaignApiV1ExtGrcCampaignsCampaignIdStartPost
    | None
):
    """Start Campaign

    Args:
        campaign_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | StartCampaignApiV1ExtGrcCampaignsCampaignIdStartPostResponseStartCampaignApiV1ExtGrcCampaignsCampaignIdStartPost
    """

    return sync_detailed(
        campaign_id=campaign_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    campaign_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | StartCampaignApiV1ExtGrcCampaignsCampaignIdStartPostResponseStartCampaignApiV1ExtGrcCampaignsCampaignIdStartPost
]:
    """Start Campaign

    Args:
        campaign_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | StartCampaignApiV1ExtGrcCampaignsCampaignIdStartPostResponseStartCampaignApiV1ExtGrcCampaignsCampaignIdStartPost]
    """

    kwargs = _get_kwargs(
        campaign_id=campaign_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    campaign_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | StartCampaignApiV1ExtGrcCampaignsCampaignIdStartPostResponseStartCampaignApiV1ExtGrcCampaignsCampaignIdStartPost
    | None
):
    """Start Campaign

    Args:
        campaign_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | StartCampaignApiV1ExtGrcCampaignsCampaignIdStartPostResponseStartCampaignApiV1ExtGrcCampaignsCampaignIdStartPost
    """

    return (
        await asyncio_detailed(
            campaign_id=campaign_id,
            client=client,
        )
    ).parsed
