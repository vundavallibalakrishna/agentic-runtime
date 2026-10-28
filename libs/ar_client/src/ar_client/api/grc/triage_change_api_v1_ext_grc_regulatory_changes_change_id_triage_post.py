from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.triage_change_api_v1_ext_grc_regulatory_changes_change_id_triage_post_body import (
    TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostBody,
)
from ...models.triage_change_api_v1_ext_grc_regulatory_changes_change_id_triage_post_response_triage_change_api_v1_ext_grc_regulatory_changes_change_id_triage_post import (
    TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostResponseTriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    change_id: UUID,
    *,
    body: TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/regulatory-changes/{change_id}:triage".format(
            change_id=quote(str(change_id), safe=""),
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
    | TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostResponseTriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePost
    | None
):
    if response.status_code == 200:
        response_200 = TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostResponseTriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePost.from_dict(
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
    | TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostResponseTriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    change_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostBody,
) -> Response[
    HTTPValidationError
    | TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostResponseTriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePost
]:
    """Triage Change

    Args:
        change_id (UUID):
        body (TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostResponseTriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePost]
    """

    kwargs = _get_kwargs(
        change_id=change_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    change_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostBody,
) -> (
    HTTPValidationError
    | TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostResponseTriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePost
    | None
):
    """Triage Change

    Args:
        change_id (UUID):
        body (TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostResponseTriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePost
    """

    return sync_detailed(
        change_id=change_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    change_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostBody,
) -> Response[
    HTTPValidationError
    | TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostResponseTriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePost
]:
    """Triage Change

    Args:
        change_id (UUID):
        body (TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostResponseTriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePost]
    """

    kwargs = _get_kwargs(
        change_id=change_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    change_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostBody,
) -> (
    HTTPValidationError
    | TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostResponseTriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePost
    | None
):
    """Triage Change

    Args:
        change_id (UUID):
        body (TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | TriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePostResponseTriageChangeApiV1ExtGrcRegulatoryChangesChangeIdTriagePost
    """

    return (
        await asyncio_detailed(
            change_id=change_id,
            client=client,
            body=body,
        )
    ).parsed
