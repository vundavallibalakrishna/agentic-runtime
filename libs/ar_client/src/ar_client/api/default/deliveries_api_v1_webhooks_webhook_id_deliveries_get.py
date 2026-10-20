from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.deliveries_api_v1_webhooks_webhook_id_deliveries_get_response_deliveries_api_v1_webhooks_webhook_id_deliveries_get import DeliveriesApiV1WebhooksWebhookIdDeliveriesGetResponseDeliveriesApiV1WebhooksWebhookIdDeliveriesGet
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID



def _get_kwargs(
    webhook_id: UUID,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/webhooks/{webhook_id}/deliveries".format(webhook_id=quote(str(webhook_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> DeliveriesApiV1WebhooksWebhookIdDeliveriesGetResponseDeliveriesApiV1WebhooksWebhookIdDeliveriesGet | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = DeliveriesApiV1WebhooksWebhookIdDeliveriesGetResponseDeliveriesApiV1WebhooksWebhookIdDeliveriesGet.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[DeliveriesApiV1WebhooksWebhookIdDeliveriesGetResponseDeliveriesApiV1WebhooksWebhookIdDeliveriesGet | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    webhook_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[DeliveriesApiV1WebhooksWebhookIdDeliveriesGetResponseDeliveriesApiV1WebhooksWebhookIdDeliveriesGet | HTTPValidationError]:
    """ Deliveries

    Args:
        webhook_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeliveriesApiV1WebhooksWebhookIdDeliveriesGetResponseDeliveriesApiV1WebhooksWebhookIdDeliveriesGet | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        webhook_id=webhook_id,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    webhook_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeliveriesApiV1WebhooksWebhookIdDeliveriesGetResponseDeliveriesApiV1WebhooksWebhookIdDeliveriesGet | HTTPValidationError | None:
    """ Deliveries

    Args:
        webhook_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeliveriesApiV1WebhooksWebhookIdDeliveriesGetResponseDeliveriesApiV1WebhooksWebhookIdDeliveriesGet | HTTPValidationError
     """


    return sync_detailed(
        webhook_id=webhook_id,
client=client,

    ).parsed

async def asyncio_detailed(
    webhook_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[DeliveriesApiV1WebhooksWebhookIdDeliveriesGetResponseDeliveriesApiV1WebhooksWebhookIdDeliveriesGet | HTTPValidationError]:
    """ Deliveries

    Args:
        webhook_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeliveriesApiV1WebhooksWebhookIdDeliveriesGetResponseDeliveriesApiV1WebhooksWebhookIdDeliveriesGet | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        webhook_id=webhook_id,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    webhook_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeliveriesApiV1WebhooksWebhookIdDeliveriesGetResponseDeliveriesApiV1WebhooksWebhookIdDeliveriesGet | HTTPValidationError | None:
    """ Deliveries

    Args:
        webhook_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeliveriesApiV1WebhooksWebhookIdDeliveriesGetResponseDeliveriesApiV1WebhooksWebhookIdDeliveriesGet | HTTPValidationError
     """


    return (await asyncio_detailed(
        webhook_id=webhook_id,
client=client,

    )).parsed
