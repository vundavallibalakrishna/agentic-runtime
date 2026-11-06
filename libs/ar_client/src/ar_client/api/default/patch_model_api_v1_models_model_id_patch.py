from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.model_patch import ModelPatch
from ...models.patch_model_api_v1_models_model_id_patch_response_patch_model_api_v1_models_model_id_patch import (
    PatchModelApiV1ModelsModelIdPatchResponsePatchModelApiV1ModelsModelIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    model_id: UUID,
    *,
    body: ModelPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/models/{model_id}".format(
            model_id=quote(str(model_id), safe=""),
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
    | PatchModelApiV1ModelsModelIdPatchResponsePatchModelApiV1ModelsModelIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = (
            PatchModelApiV1ModelsModelIdPatchResponsePatchModelApiV1ModelsModelIdPatch.from_dict(
                response.json()
            )
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
    HTTPValidationError | PatchModelApiV1ModelsModelIdPatchResponsePatchModelApiV1ModelsModelIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    model_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ModelPatch,
) -> Response[
    HTTPValidationError | PatchModelApiV1ModelsModelIdPatchResponsePatchModelApiV1ModelsModelIdPatch
]:
    """Patch Model

     Change a model's name, its upstream model, its prices or its request options.

    Args:
        model_id (UUID):
        body (ModelPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchModelApiV1ModelsModelIdPatchResponsePatchModelApiV1ModelsModelIdPatch]
    """

    kwargs = _get_kwargs(
        model_id=model_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    model_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ModelPatch,
) -> (
    HTTPValidationError
    | PatchModelApiV1ModelsModelIdPatchResponsePatchModelApiV1ModelsModelIdPatch
    | None
):
    """Patch Model

     Change a model's name, its upstream model, its prices or its request options.

    Args:
        model_id (UUID):
        body (ModelPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchModelApiV1ModelsModelIdPatchResponsePatchModelApiV1ModelsModelIdPatch
    """

    return sync_detailed(
        model_id=model_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    model_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ModelPatch,
) -> Response[
    HTTPValidationError | PatchModelApiV1ModelsModelIdPatchResponsePatchModelApiV1ModelsModelIdPatch
]:
    """Patch Model

     Change a model's name, its upstream model, its prices or its request options.

    Args:
        model_id (UUID):
        body (ModelPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchModelApiV1ModelsModelIdPatchResponsePatchModelApiV1ModelsModelIdPatch]
    """

    kwargs = _get_kwargs(
        model_id=model_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    model_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: ModelPatch,
) -> (
    HTTPValidationError
    | PatchModelApiV1ModelsModelIdPatchResponsePatchModelApiV1ModelsModelIdPatch
    | None
):
    """Patch Model

     Change a model's name, its upstream model, its prices or its request options.

    Args:
        model_id (UUID):
        body (ModelPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchModelApiV1ModelsModelIdPatchResponsePatchModelApiV1ModelsModelIdPatch
    """

    return (
        await asyncio_detailed(
            model_id=model_id,
            client=client,
            body=body,
        )
    ).parsed
