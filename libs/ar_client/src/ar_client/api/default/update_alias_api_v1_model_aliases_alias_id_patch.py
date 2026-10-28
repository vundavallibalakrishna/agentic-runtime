from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.alias_patch import AliasPatch
from ...models.http_validation_error import HTTPValidationError
from ...models.update_alias_api_v1_model_aliases_alias_id_patch_response_update_alias_api_v1_model_aliases_alias_id_patch import (
    UpdateAliasApiV1ModelAliasesAliasIdPatchResponseUpdateAliasApiV1ModelAliasesAliasIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    alias_id: UUID,
    *,
    body: AliasPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/model-aliases/{alias_id}".format(
            alias_id=quote(str(alias_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | UpdateAliasApiV1ModelAliasesAliasIdPatchResponseUpdateAliasApiV1ModelAliasesAliasIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = UpdateAliasApiV1ModelAliasesAliasIdPatchResponseUpdateAliasApiV1ModelAliasesAliasIdPatch.from_dict(
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
    HTTPValidationError
    | UpdateAliasApiV1ModelAliasesAliasIdPatchResponseUpdateAliasApiV1ModelAliasesAliasIdPatch
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
    body: AliasPatch,
) -> Response[
    HTTPValidationError
    | UpdateAliasApiV1ModelAliasesAliasIdPatchResponseUpdateAliasApiV1ModelAliasesAliasIdPatch
]:
    """Update Alias

    Args:
        alias_id (UUID):
        body (AliasPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UpdateAliasApiV1ModelAliasesAliasIdPatchResponseUpdateAliasApiV1ModelAliasesAliasIdPatch]
    """

    kwargs = _get_kwargs(
        alias_id=alias_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    alias_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AliasPatch,
) -> (
    HTTPValidationError
    | UpdateAliasApiV1ModelAliasesAliasIdPatchResponseUpdateAliasApiV1ModelAliasesAliasIdPatch
    | None
):
    """Update Alias

    Args:
        alias_id (UUID):
        body (AliasPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UpdateAliasApiV1ModelAliasesAliasIdPatchResponseUpdateAliasApiV1ModelAliasesAliasIdPatch
    """

    return sync_detailed(
        alias_id=alias_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    alias_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AliasPatch,
) -> Response[
    HTTPValidationError
    | UpdateAliasApiV1ModelAliasesAliasIdPatchResponseUpdateAliasApiV1ModelAliasesAliasIdPatch
]:
    """Update Alias

    Args:
        alias_id (UUID):
        body (AliasPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UpdateAliasApiV1ModelAliasesAliasIdPatchResponseUpdateAliasApiV1ModelAliasesAliasIdPatch]
    """

    kwargs = _get_kwargs(
        alias_id=alias_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    alias_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AliasPatch,
) -> (
    HTTPValidationError
    | UpdateAliasApiV1ModelAliasesAliasIdPatchResponseUpdateAliasApiV1ModelAliasesAliasIdPatch
    | None
):
    """Update Alias

    Args:
        alias_id (UUID):
        body (AliasPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UpdateAliasApiV1ModelAliasesAliasIdPatchResponseUpdateAliasApiV1ModelAliasesAliasIdPatch
    """

    return (
        await asyncio_detailed(
            alias_id=alias_id,
            client=client,
            body=body,
        )
    ).parsed
