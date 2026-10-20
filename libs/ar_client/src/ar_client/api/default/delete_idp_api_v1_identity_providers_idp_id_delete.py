from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_idp_api_v1_identity_providers_idp_id_delete_response_delete_idp_api_v1_identity_providers_idp_id_delete import DeleteIdpApiV1IdentityProvidersIdpIdDeleteResponseDeleteIdpApiV1IdentityProvidersIdpIdDelete
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID



def _get_kwargs(
    idp_id: UUID,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/identity-providers/{idp_id}".format(idp_id=quote(str(idp_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> DeleteIdpApiV1IdentityProvidersIdpIdDeleteResponseDeleteIdpApiV1IdentityProvidersIdpIdDelete | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = DeleteIdpApiV1IdentityProvidersIdpIdDeleteResponseDeleteIdpApiV1IdentityProvidersIdpIdDelete.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[DeleteIdpApiV1IdentityProvidersIdpIdDeleteResponseDeleteIdpApiV1IdentityProvidersIdpIdDelete | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    idp_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[DeleteIdpApiV1IdentityProvidersIdpIdDeleteResponseDeleteIdpApiV1IdentityProvidersIdpIdDelete | HTTPValidationError]:
    """ Delete Idp

    Args:
        idp_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteIdpApiV1IdentityProvidersIdpIdDeleteResponseDeleteIdpApiV1IdentityProvidersIdpIdDelete | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        idp_id=idp_id,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    idp_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeleteIdpApiV1IdentityProvidersIdpIdDeleteResponseDeleteIdpApiV1IdentityProvidersIdpIdDelete | HTTPValidationError | None:
    """ Delete Idp

    Args:
        idp_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteIdpApiV1IdentityProvidersIdpIdDeleteResponseDeleteIdpApiV1IdentityProvidersIdpIdDelete | HTTPValidationError
     """


    return sync_detailed(
        idp_id=idp_id,
client=client,

    ).parsed

async def asyncio_detailed(
    idp_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[DeleteIdpApiV1IdentityProvidersIdpIdDeleteResponseDeleteIdpApiV1IdentityProvidersIdpIdDelete | HTTPValidationError]:
    """ Delete Idp

    Args:
        idp_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteIdpApiV1IdentityProvidersIdpIdDeleteResponseDeleteIdpApiV1IdentityProvidersIdpIdDelete | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        idp_id=idp_id,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    idp_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeleteIdpApiV1IdentityProvidersIdpIdDeleteResponseDeleteIdpApiV1IdentityProvidersIdpIdDelete | HTTPValidationError | None:
    """ Delete Idp

    Args:
        idp_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteIdpApiV1IdentityProvidersIdpIdDeleteResponseDeleteIdpApiV1IdentityProvidersIdpIdDelete | HTTPValidationError
     """


    return (await asyncio_detailed(
        idp_id=idp_id,
client=client,

    )).parsed
