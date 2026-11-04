from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.add_version_api_v1_ext_grc_policies_policy_id_versions_post_body import (
    AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostBody,
)
from ...models.add_version_api_v1_ext_grc_policies_policy_id_versions_post_response_add_version_api_v1_ext_grc_policies_policy_id_versions_post import (
    AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostResponseAddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    policy_id: UUID,
    *,
    body: AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/policies/{policy_id}/versions".format(
            policy_id=quote(str(policy_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostResponseAddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostResponseAddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPost.from_dict(
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
    AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostResponseAddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    policy_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostBody,
) -> Response[
    AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostResponseAddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPost
    | HTTPValidationError
]:
    """Add Version

    Args:
        policy_id (UUID):
        body (AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostResponseAddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        policy_id=policy_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    policy_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostBody,
) -> (
    AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostResponseAddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPost
    | HTTPValidationError
    | None
):
    """Add Version

    Args:
        policy_id (UUID):
        body (AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostResponseAddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPost | HTTPValidationError
    """

    return sync_detailed(
        policy_id=policy_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    policy_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostBody,
) -> Response[
    AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostResponseAddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPost
    | HTTPValidationError
]:
    """Add Version

    Args:
        policy_id (UUID):
        body (AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostResponseAddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        policy_id=policy_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    policy_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostBody,
) -> (
    AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostResponseAddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPost
    | HTTPValidationError
    | None
):
    """Add Version

    Args:
        policy_id (UUID):
        body (AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPostResponseAddVersionApiV1ExtGrcPoliciesPolicyIdVersionsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            policy_id=policy_id,
            client=client,
            body=body,
        )
    ).parsed
