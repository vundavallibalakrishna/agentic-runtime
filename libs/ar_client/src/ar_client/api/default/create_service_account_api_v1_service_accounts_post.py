from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_service_account_api_v1_service_accounts_post_response_create_service_account_api_v1_service_accounts_post import CreateServiceAccountApiV1ServiceAccountsPostResponseCreateServiceAccountApiV1ServiceAccountsPost
from ...models.http_validation_error import HTTPValidationError
from ...models.service_account_create import ServiceAccountCreate
from typing import cast



def _get_kwargs(
    *,
    body: ServiceAccountCreate,

) -> dict[str, Any]:
    headers: dict[str, Any] = {}


    

    

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/service-accounts",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> CreateServiceAccountApiV1ServiceAccountsPostResponseCreateServiceAccountApiV1ServiceAccountsPost | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = CreateServiceAccountApiV1ServiceAccountsPostResponseCreateServiceAccountApiV1ServiceAccountsPost.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[CreateServiceAccountApiV1ServiceAccountsPostResponseCreateServiceAccountApiV1ServiceAccountsPost | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ServiceAccountCreate,

) -> Response[CreateServiceAccountApiV1ServiceAccountsPostResponseCreateServiceAccountApiV1ServiceAccountsPost | HTTPValidationError]:
    """ Create Service Account

    Args:
        body (ServiceAccountCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateServiceAccountApiV1ServiceAccountsPostResponseCreateServiceAccountApiV1ServiceAccountsPost | HTTPValidationError]
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
    body: ServiceAccountCreate,

) -> CreateServiceAccountApiV1ServiceAccountsPostResponseCreateServiceAccountApiV1ServiceAccountsPost | HTTPValidationError | None:
    """ Create Service Account

    Args:
        body (ServiceAccountCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateServiceAccountApiV1ServiceAccountsPostResponseCreateServiceAccountApiV1ServiceAccountsPost | HTTPValidationError
     """


    return sync_detailed(
        client=client,
body=body,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ServiceAccountCreate,

) -> Response[CreateServiceAccountApiV1ServiceAccountsPostResponseCreateServiceAccountApiV1ServiceAccountsPost | HTTPValidationError]:
    """ Create Service Account

    Args:
        body (ServiceAccountCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateServiceAccountApiV1ServiceAccountsPostResponseCreateServiceAccountApiV1ServiceAccountsPost | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        body=body,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: ServiceAccountCreate,

) -> CreateServiceAccountApiV1ServiceAccountsPostResponseCreateServiceAccountApiV1ServiceAccountsPost | HTTPValidationError | None:
    """ Create Service Account

    Args:
        body (ServiceAccountCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateServiceAccountApiV1ServiceAccountsPostResponseCreateServiceAccountApiV1ServiceAccountsPost | HTTPValidationError
     """


    return (await asyncio_detailed(
        client=client,
body=body,

    )).parsed
