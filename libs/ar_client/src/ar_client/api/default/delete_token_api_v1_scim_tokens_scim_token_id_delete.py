from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_token_api_v1_scim_tokens_scim_token_id_delete_response_delete_token_api_v1_scim_tokens_scim_token_id_delete import DeleteTokenApiV1ScimTokensScimTokenIdDeleteResponseDeleteTokenApiV1ScimTokensScimTokenIdDelete
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID



def _get_kwargs(
    scim_token_id: UUID,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/scim-tokens/{scim_token_id}".format(scim_token_id=quote(str(scim_token_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> DeleteTokenApiV1ScimTokensScimTokenIdDeleteResponseDeleteTokenApiV1ScimTokensScimTokenIdDelete | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = DeleteTokenApiV1ScimTokensScimTokenIdDeleteResponseDeleteTokenApiV1ScimTokensScimTokenIdDelete.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[DeleteTokenApiV1ScimTokensScimTokenIdDeleteResponseDeleteTokenApiV1ScimTokensScimTokenIdDelete | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    scim_token_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[DeleteTokenApiV1ScimTokensScimTokenIdDeleteResponseDeleteTokenApiV1ScimTokensScimTokenIdDelete | HTTPValidationError]:
    """ Delete Token

    Args:
        scim_token_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteTokenApiV1ScimTokensScimTokenIdDeleteResponseDeleteTokenApiV1ScimTokensScimTokenIdDelete | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        scim_token_id=scim_token_id,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    scim_token_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeleteTokenApiV1ScimTokensScimTokenIdDeleteResponseDeleteTokenApiV1ScimTokensScimTokenIdDelete | HTTPValidationError | None:
    """ Delete Token

    Args:
        scim_token_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteTokenApiV1ScimTokensScimTokenIdDeleteResponseDeleteTokenApiV1ScimTokensScimTokenIdDelete | HTTPValidationError
     """


    return sync_detailed(
        scim_token_id=scim_token_id,
client=client,

    ).parsed

async def asyncio_detailed(
    scim_token_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[DeleteTokenApiV1ScimTokensScimTokenIdDeleteResponseDeleteTokenApiV1ScimTokensScimTokenIdDelete | HTTPValidationError]:
    """ Delete Token

    Args:
        scim_token_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteTokenApiV1ScimTokensScimTokenIdDeleteResponseDeleteTokenApiV1ScimTokensScimTokenIdDelete | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        scim_token_id=scim_token_id,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    scim_token_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeleteTokenApiV1ScimTokensScimTokenIdDeleteResponseDeleteTokenApiV1ScimTokensScimTokenIdDelete | HTTPValidationError | None:
    """ Delete Token

    Args:
        scim_token_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteTokenApiV1ScimTokensScimTokenIdDeleteResponseDeleteTokenApiV1ScimTokensScimTokenIdDelete | HTTPValidationError
     """


    return (await asyncio_detailed(
        scim_token_id=scim_token_id,
client=client,

    )).parsed
