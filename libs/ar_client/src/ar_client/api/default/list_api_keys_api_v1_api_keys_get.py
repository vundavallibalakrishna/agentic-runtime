from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_api_keys_api_v1_api_keys_get_response_list_api_keys_api_v1_api_keys_get import ListApiKeysApiV1ApiKeysGetResponseListApiKeysApiV1ApiKeysGet
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID



def _get_kwargs(
    *,
    service_account_id: None | Unset | UUID = UNSET,

) -> dict[str, Any]:
    

    

    params: dict[str, Any] = {}

    json_service_account_id: None | str | Unset
    if isinstance(service_account_id, Unset):
        json_service_account_id = UNSET
    elif isinstance(service_account_id, UUID):
        json_service_account_id = str(service_account_id)
    else:
        json_service_account_id = service_account_id
    params["service_account_id"] = json_service_account_id


    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}


    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/api-keys",
        "params": params,
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | ListApiKeysApiV1ApiKeysGetResponseListApiKeysApiV1ApiKeysGet | None:
    if response.status_code == 200:
        response_200 = ListApiKeysApiV1ApiKeysGetResponseListApiKeysApiV1ApiKeysGet.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | ListApiKeysApiV1ApiKeysGetResponseListApiKeysApiV1ApiKeysGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    service_account_id: None | Unset | UUID = UNSET,

) -> Response[HTTPValidationError | ListApiKeysApiV1ApiKeysGetResponseListApiKeysApiV1ApiKeysGet]:
    """ List Api Keys

    Args:
        service_account_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListApiKeysApiV1ApiKeysGetResponseListApiKeysApiV1ApiKeysGet]
     """


    kwargs = _get_kwargs(
        service_account_id=service_account_id,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    *,
    client: AuthenticatedClient | Client,
    service_account_id: None | Unset | UUID = UNSET,

) -> HTTPValidationError | ListApiKeysApiV1ApiKeysGetResponseListApiKeysApiV1ApiKeysGet | None:
    """ List Api Keys

    Args:
        service_account_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListApiKeysApiV1ApiKeysGetResponseListApiKeysApiV1ApiKeysGet
     """


    return sync_detailed(
        client=client,
service_account_id=service_account_id,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    service_account_id: None | Unset | UUID = UNSET,

) -> Response[HTTPValidationError | ListApiKeysApiV1ApiKeysGetResponseListApiKeysApiV1ApiKeysGet]:
    """ List Api Keys

    Args:
        service_account_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListApiKeysApiV1ApiKeysGetResponseListApiKeysApiV1ApiKeysGet]
     """


    kwargs = _get_kwargs(
        service_account_id=service_account_id,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    service_account_id: None | Unset | UUID = UNSET,

) -> HTTPValidationError | ListApiKeysApiV1ApiKeysGetResponseListApiKeysApiV1ApiKeysGet | None:
    """ List Api Keys

    Args:
        service_account_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListApiKeysApiV1ApiKeysGetResponseListApiKeysApiV1ApiKeysGet
     """


    return (await asyncio_detailed(
        client=client,
service_account_id=service_account_id,

    )).parsed
