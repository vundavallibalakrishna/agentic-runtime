from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_alias_api_v1_model_aliases_alias_id_delete_response_delete_alias_api_v1_model_aliases_alias_id_delete import (
    DeleteAliasApiV1ModelAliasesAliasIdDeleteResponseDeleteAliasApiV1ModelAliasesAliasIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    alias_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/model-aliases/{alias_id}".format(
            alias_id=quote(str(alias_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeleteAliasApiV1ModelAliasesAliasIdDeleteResponseDeleteAliasApiV1ModelAliasesAliasIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DeleteAliasApiV1ModelAliasesAliasIdDeleteResponseDeleteAliasApiV1ModelAliasesAliasIdDelete.from_dict(
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
    DeleteAliasApiV1ModelAliasesAliasIdDeleteResponseDeleteAliasApiV1ModelAliasesAliasIdDelete
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    alias_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteAliasApiV1ModelAliasesAliasIdDeleteResponseDeleteAliasApiV1ModelAliasesAliasIdDelete
    | HTTPValidationError
]:
    """Delete Alias

     Remove an alias.

    Args:
        alias_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteAliasApiV1ModelAliasesAliasIdDeleteResponseDeleteAliasApiV1ModelAliasesAliasIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        alias_id=alias_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    alias_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteAliasApiV1ModelAliasesAliasIdDeleteResponseDeleteAliasApiV1ModelAliasesAliasIdDelete
    | HTTPValidationError
    | None
):
    """Delete Alias

     Remove an alias.

    Args:
        alias_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteAliasApiV1ModelAliasesAliasIdDeleteResponseDeleteAliasApiV1ModelAliasesAliasIdDelete | HTTPValidationError
    """

    return sync_detailed(
        alias_id=alias_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    alias_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteAliasApiV1ModelAliasesAliasIdDeleteResponseDeleteAliasApiV1ModelAliasesAliasIdDelete
    | HTTPValidationError
]:
    """Delete Alias

     Remove an alias.

    Args:
        alias_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteAliasApiV1ModelAliasesAliasIdDeleteResponseDeleteAliasApiV1ModelAliasesAliasIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        alias_id=alias_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    alias_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteAliasApiV1ModelAliasesAliasIdDeleteResponseDeleteAliasApiV1ModelAliasesAliasIdDelete
    | HTTPValidationError
    | None
):
    """Delete Alias

     Remove an alias.

    Args:
        alias_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteAliasApiV1ModelAliasesAliasIdDeleteResponseDeleteAliasApiV1ModelAliasesAliasIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            alias_id=alias_id,
            client=client,
        )
    ).parsed
