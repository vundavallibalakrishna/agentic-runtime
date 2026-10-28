from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_finding_api_v1_ext_grc_findings_post_body import (
    CreateFindingApiV1ExtGrcFindingsPostBody,
)
from ...models.create_finding_api_v1_ext_grc_findings_post_response_create_finding_api_v1_ext_grc_findings_post import (
    CreateFindingApiV1ExtGrcFindingsPostResponseCreateFindingApiV1ExtGrcFindingsPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    *,
    body: CreateFindingApiV1ExtGrcFindingsPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/findings",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateFindingApiV1ExtGrcFindingsPostResponseCreateFindingApiV1ExtGrcFindingsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CreateFindingApiV1ExtGrcFindingsPostResponseCreateFindingApiV1ExtGrcFindingsPost.from_dict(
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
    CreateFindingApiV1ExtGrcFindingsPostResponseCreateFindingApiV1ExtGrcFindingsPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateFindingApiV1ExtGrcFindingsPostBody,
) -> Response[
    CreateFindingApiV1ExtGrcFindingsPostResponseCreateFindingApiV1ExtGrcFindingsPost
    | HTTPValidationError
]:
    """Create Finding

    Args:
        body (CreateFindingApiV1ExtGrcFindingsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateFindingApiV1ExtGrcFindingsPostResponseCreateFindingApiV1ExtGrcFindingsPost | HTTPValidationError]
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
    body: CreateFindingApiV1ExtGrcFindingsPostBody,
) -> (
    CreateFindingApiV1ExtGrcFindingsPostResponseCreateFindingApiV1ExtGrcFindingsPost
    | HTTPValidationError
    | None
):
    """Create Finding

    Args:
        body (CreateFindingApiV1ExtGrcFindingsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateFindingApiV1ExtGrcFindingsPostResponseCreateFindingApiV1ExtGrcFindingsPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateFindingApiV1ExtGrcFindingsPostBody,
) -> Response[
    CreateFindingApiV1ExtGrcFindingsPostResponseCreateFindingApiV1ExtGrcFindingsPost
    | HTTPValidationError
]:
    """Create Finding

    Args:
        body (CreateFindingApiV1ExtGrcFindingsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateFindingApiV1ExtGrcFindingsPostResponseCreateFindingApiV1ExtGrcFindingsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: CreateFindingApiV1ExtGrcFindingsPostBody,
) -> (
    CreateFindingApiV1ExtGrcFindingsPostResponseCreateFindingApiV1ExtGrcFindingsPost
    | HTTPValidationError
    | None
):
    """Create Finding

    Args:
        body (CreateFindingApiV1ExtGrcFindingsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateFindingApiV1ExtGrcFindingsPostResponseCreateFindingApiV1ExtGrcFindingsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
