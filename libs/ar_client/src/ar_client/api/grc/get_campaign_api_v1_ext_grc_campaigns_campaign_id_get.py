from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_campaign_api_v1_ext_grc_campaigns_campaign_id_get_response_get_campaign_api_v1_ext_grc_campaigns_campaign_id_get import (
    GetCampaignApiV1ExtGrcCampaignsCampaignIdGetResponseGetCampaignApiV1ExtGrcCampaignsCampaignIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    campaign_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/campaigns/{campaign_id}".format(
            campaign_id=quote(str(campaign_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetCampaignApiV1ExtGrcCampaignsCampaignIdGetResponseGetCampaignApiV1ExtGrcCampaignsCampaignIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetCampaignApiV1ExtGrcCampaignsCampaignIdGetResponseGetCampaignApiV1ExtGrcCampaignsCampaignIdGet.from_dict(
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
    GetCampaignApiV1ExtGrcCampaignsCampaignIdGetResponseGetCampaignApiV1ExtGrcCampaignsCampaignIdGet
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
) -> Response[
    GetCampaignApiV1ExtGrcCampaignsCampaignIdGetResponseGetCampaignApiV1ExtGrcCampaignsCampaignIdGet
    | HTTPValidationError
]:
    """Get Campaign

    Args:
        campaign_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetCampaignApiV1ExtGrcCampaignsCampaignIdGetResponseGetCampaignApiV1ExtGrcCampaignsCampaignIdGet | HTTPValidationError]
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
    GetCampaignApiV1ExtGrcCampaignsCampaignIdGetResponseGetCampaignApiV1ExtGrcCampaignsCampaignIdGet
    | HTTPValidationError
    | None
):
    """Get Campaign

    Args:
        campaign_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetCampaignApiV1ExtGrcCampaignsCampaignIdGetResponseGetCampaignApiV1ExtGrcCampaignsCampaignIdGet | HTTPValidationError
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
    GetCampaignApiV1ExtGrcCampaignsCampaignIdGetResponseGetCampaignApiV1ExtGrcCampaignsCampaignIdGet
    | HTTPValidationError
]:
    """Get Campaign

    Args:
        campaign_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetCampaignApiV1ExtGrcCampaignsCampaignIdGetResponseGetCampaignApiV1ExtGrcCampaignsCampaignIdGet | HTTPValidationError]
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
    GetCampaignApiV1ExtGrcCampaignsCampaignIdGetResponseGetCampaignApiV1ExtGrcCampaignsCampaignIdGet
    | HTTPValidationError
    | None
):
    """Get Campaign

    Args:
        campaign_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetCampaignApiV1ExtGrcCampaignsCampaignIdGetResponseGetCampaignApiV1ExtGrcCampaignsCampaignIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            campaign_id=campaign_id,
            client=client,
        )
    ).parsed
