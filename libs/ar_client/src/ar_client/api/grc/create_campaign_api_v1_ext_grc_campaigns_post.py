from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_campaign_api_v1_ext_grc_campaigns_post_body import (
    CreateCampaignApiV1ExtGrcCampaignsPostBody,
)
from ...models.create_campaign_api_v1_ext_grc_campaigns_post_response_create_campaign_api_v1_ext_grc_campaigns_post import (
    CreateCampaignApiV1ExtGrcCampaignsPostResponseCreateCampaignApiV1ExtGrcCampaignsPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    *,
    body: CreateCampaignApiV1ExtGrcCampaignsPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/campaigns",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateCampaignApiV1ExtGrcCampaignsPostResponseCreateCampaignApiV1ExtGrcCampaignsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CreateCampaignApiV1ExtGrcCampaignsPostResponseCreateCampaignApiV1ExtGrcCampaignsPost.from_dict(
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
    CreateCampaignApiV1ExtGrcCampaignsPostResponseCreateCampaignApiV1ExtGrcCampaignsPost
    | HTTPValidationError
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
    body: CreateCampaignApiV1ExtGrcCampaignsPostBody,
) -> Response[
    CreateCampaignApiV1ExtGrcCampaignsPostResponseCreateCampaignApiV1ExtGrcCampaignsPost
    | HTTPValidationError
]:
    """Create Campaign

    Args:
        body (CreateCampaignApiV1ExtGrcCampaignsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateCampaignApiV1ExtGrcCampaignsPostResponseCreateCampaignApiV1ExtGrcCampaignsPost | HTTPValidationError]
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
    body: CreateCampaignApiV1ExtGrcCampaignsPostBody,
) -> (
    CreateCampaignApiV1ExtGrcCampaignsPostResponseCreateCampaignApiV1ExtGrcCampaignsPost
    | HTTPValidationError
    | None
):
    """Create Campaign

    Args:
        body (CreateCampaignApiV1ExtGrcCampaignsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateCampaignApiV1ExtGrcCampaignsPostResponseCreateCampaignApiV1ExtGrcCampaignsPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateCampaignApiV1ExtGrcCampaignsPostBody,
) -> Response[
    CreateCampaignApiV1ExtGrcCampaignsPostResponseCreateCampaignApiV1ExtGrcCampaignsPost
    | HTTPValidationError
]:
    """Create Campaign

    Args:
        body (CreateCampaignApiV1ExtGrcCampaignsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateCampaignApiV1ExtGrcCampaignsPostResponseCreateCampaignApiV1ExtGrcCampaignsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: CreateCampaignApiV1ExtGrcCampaignsPostBody,
) -> (
    CreateCampaignApiV1ExtGrcCampaignsPostResponseCreateCampaignApiV1ExtGrcCampaignsPost
    | HTTPValidationError
    | None
):
    """Create Campaign

    Args:
        body (CreateCampaignApiV1ExtGrcCampaignsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateCampaignApiV1ExtGrcCampaignsPostResponseCreateCampaignApiV1ExtGrcCampaignsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
