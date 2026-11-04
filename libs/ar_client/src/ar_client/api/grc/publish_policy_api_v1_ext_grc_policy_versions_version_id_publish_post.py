from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.publish_policy_api_v1_ext_grc_policy_versions_version_id_publish_post_response_publish_policy_api_v1_ext_grc_policy_versions_version_id_publish_post import (
    PublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPostResponsePublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    version_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/policy-versions/{version_id}:publish".format(
            version_id=quote(str(version_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | PublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPostResponsePublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPost
    | None
):
    if response.status_code == 200:
        response_200 = PublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPostResponsePublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPost.from_dict(
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
    | PublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPostResponsePublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | PublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPostResponsePublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPost
]:
    """Publish Policy

    Args:
        version_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPostResponsePublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPost]
    """

    kwargs = _get_kwargs(
        version_id=version_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | PublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPostResponsePublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPost
    | None
):
    """Publish Policy

    Args:
        version_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPostResponsePublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPost
    """

    return sync_detailed(
        version_id=version_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | PublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPostResponsePublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPost
]:
    """Publish Policy

    Args:
        version_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPostResponsePublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPost]
    """

    kwargs = _get_kwargs(
        version_id=version_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    version_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | PublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPostResponsePublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPost
    | None
):
    """Publish Policy

    Args:
        version_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPostResponsePublishPolicyApiV1ExtGrcPolicyVersionsVersionIdPublishPost
    """

    return (
        await asyncio_detailed(
            version_id=version_id,
            client=client,
        )
    ).parsed
