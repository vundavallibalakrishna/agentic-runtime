from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.entity_posture_api_v1_ext_grc_entities_entity_id_posture_get_response_entity_posture_api_v1_ext_grc_entities_entity_id_posture_get import (
    EntityPostureApiV1ExtGrcEntitiesEntityIdPostureGetResponseEntityPostureApiV1ExtGrcEntitiesEntityIdPostureGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    entity_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/entities/{entity_id}/posture".format(
            entity_id=quote(str(entity_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    EntityPostureApiV1ExtGrcEntitiesEntityIdPostureGetResponseEntityPostureApiV1ExtGrcEntitiesEntityIdPostureGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = EntityPostureApiV1ExtGrcEntitiesEntityIdPostureGetResponseEntityPostureApiV1ExtGrcEntitiesEntityIdPostureGet.from_dict(
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
    EntityPostureApiV1ExtGrcEntitiesEntityIdPostureGetResponseEntityPostureApiV1ExtGrcEntitiesEntityIdPostureGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    entity_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    EntityPostureApiV1ExtGrcEntitiesEntityIdPostureGetResponseEntityPostureApiV1ExtGrcEntitiesEntityIdPostureGet
    | HTTPValidationError
]:
    """Entity Posture

    Args:
        entity_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[EntityPostureApiV1ExtGrcEntitiesEntityIdPostureGetResponseEntityPostureApiV1ExtGrcEntitiesEntityIdPostureGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        entity_id=entity_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    entity_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    EntityPostureApiV1ExtGrcEntitiesEntityIdPostureGetResponseEntityPostureApiV1ExtGrcEntitiesEntityIdPostureGet
    | HTTPValidationError
    | None
):
    """Entity Posture

    Args:
        entity_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        EntityPostureApiV1ExtGrcEntitiesEntityIdPostureGetResponseEntityPostureApiV1ExtGrcEntitiesEntityIdPostureGet | HTTPValidationError
    """

    return sync_detailed(
        entity_id=entity_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    entity_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    EntityPostureApiV1ExtGrcEntitiesEntityIdPostureGetResponseEntityPostureApiV1ExtGrcEntitiesEntityIdPostureGet
    | HTTPValidationError
]:
    """Entity Posture

    Args:
        entity_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[EntityPostureApiV1ExtGrcEntitiesEntityIdPostureGetResponseEntityPostureApiV1ExtGrcEntitiesEntityIdPostureGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        entity_id=entity_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    entity_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    EntityPostureApiV1ExtGrcEntitiesEntityIdPostureGetResponseEntityPostureApiV1ExtGrcEntitiesEntityIdPostureGet
    | HTTPValidationError
    | None
):
    """Entity Posture

    Args:
        entity_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        EntityPostureApiV1ExtGrcEntitiesEntityIdPostureGetResponseEntityPostureApiV1ExtGrcEntitiesEntityIdPostureGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            entity_id=entity_id,
            client=client,
        )
    ).parsed
