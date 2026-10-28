from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.close_campaign_api_v1_ext_grc_campaigns_campaign_id_close_post_body import (
    CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostBody,
)
from ...models.close_campaign_api_v1_ext_grc_campaigns_campaign_id_close_post_response_close_campaign_api_v1_ext_grc_campaigns_campaign_id_close_post import (
    CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostResponseCloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    campaign_id: UUID,
    *,
    body: CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/campaigns/{campaign_id}:close".format(
            campaign_id=quote(str(campaign_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostResponseCloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostResponseCloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePost.from_dict(
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
    CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostResponseCloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePost
    | HTTPValidationError
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
    body: CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostBody,
) -> Response[
    CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostResponseCloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePost
    | HTTPValidationError
]:
    """Close Campaign

    Args:
        campaign_id (UUID):
        body (CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostResponseCloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        campaign_id=campaign_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    campaign_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostBody,
) -> (
    CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostResponseCloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePost
    | HTTPValidationError
    | None
):
    """Close Campaign

    Args:
        campaign_id (UUID):
        body (CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostResponseCloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePost | HTTPValidationError
    """

    return sync_detailed(
        campaign_id=campaign_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    campaign_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostBody,
) -> Response[
    CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostResponseCloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePost
    | HTTPValidationError
]:
    """Close Campaign

    Args:
        campaign_id (UUID):
        body (CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostResponseCloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        campaign_id=campaign_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    campaign_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostBody,
) -> (
    CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostResponseCloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePost
    | HTTPValidationError
    | None
):
    """Close Campaign

    Args:
        campaign_id (UUID):
        body (CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePostResponseCloseCampaignApiV1ExtGrcCampaignsCampaignIdClosePost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            campaign_id=campaign_id,
            client=client,
            body=body,
        )
    ).parsed
