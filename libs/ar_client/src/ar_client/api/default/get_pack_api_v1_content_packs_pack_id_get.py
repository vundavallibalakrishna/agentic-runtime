from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.get_pack_api_v1_content_packs_pack_id_get_response_get_pack_api_v1_content_packs_pack_id_get import (
    GetPackApiV1ContentPacksPackIdGetResponseGetPackApiV1ContentPacksPackIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from ...types import Response


def _get_kwargs(
    pack_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/content-packs/{pack_id}".format(
            pack_id=quote(str(pack_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetPackApiV1ContentPacksPackIdGetResponseGetPackApiV1ContentPacksPackIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = (
            GetPackApiV1ContentPacksPackIdGetResponseGetPackApiV1ContentPacksPackIdGet.from_dict(
                response.json()
            )
        )

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    GetPackApiV1ContentPacksPackIdGetResponseGetPackApiV1ContentPacksPackIdGet | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    pack_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetPackApiV1ContentPacksPackIdGetResponseGetPackApiV1ContentPacksPackIdGet | HTTPValidationError
]:
    """Get Pack

    Args:
        pack_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetPackApiV1ContentPacksPackIdGetResponseGetPackApiV1ContentPacksPackIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        pack_id=pack_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    pack_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetPackApiV1ContentPacksPackIdGetResponseGetPackApiV1ContentPacksPackIdGet
    | HTTPValidationError
    | None
):
    """Get Pack

    Args:
        pack_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetPackApiV1ContentPacksPackIdGetResponseGetPackApiV1ContentPacksPackIdGet | HTTPValidationError
    """

    return sync_detailed(
        pack_id=pack_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    pack_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetPackApiV1ContentPacksPackIdGetResponseGetPackApiV1ContentPacksPackIdGet | HTTPValidationError
]:
    """Get Pack

    Args:
        pack_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetPackApiV1ContentPacksPackIdGetResponseGetPackApiV1ContentPacksPackIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        pack_id=pack_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    pack_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetPackApiV1ContentPacksPackIdGetResponseGetPackApiV1ContentPacksPackIdGet
    | HTTPValidationError
    | None
):
    """Get Pack

    Args:
        pack_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetPackApiV1ContentPacksPackIdGetResponseGetPackApiV1ContentPacksPackIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            pack_id=pack_id,
            client=client,
        )
    ).parsed
