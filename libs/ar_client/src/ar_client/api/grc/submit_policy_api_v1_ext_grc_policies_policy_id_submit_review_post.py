from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.submit_policy_api_v1_ext_grc_policies_policy_id_submit_review_post_response_submit_policy_api_v1_ext_grc_policies_policy_id_submit_review_post import (
    SubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPostResponseSubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    policy_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/policies/{policy_id}:submit-review".format(
            policy_id=quote(str(policy_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | SubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPostResponseSubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPost
    | None
):
    if response.status_code == 200:
        response_200 = SubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPostResponseSubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPost.from_dict(
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
    | SubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPostResponseSubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPost
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
) -> Response[
    HTTPValidationError
    | SubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPostResponseSubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPost
]:
    """Submit Policy

    Args:
        policy_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPostResponseSubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPost]
    """

    kwargs = _get_kwargs(
        policy_id=policy_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    policy_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | SubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPostResponseSubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPost
    | None
):
    """Submit Policy

    Args:
        policy_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPostResponseSubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPost
    """

    return sync_detailed(
        policy_id=policy_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    policy_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | SubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPostResponseSubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPost
]:
    """Submit Policy

    Args:
        policy_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPostResponseSubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPost]
    """

    kwargs = _get_kwargs(
        policy_id=policy_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    policy_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | SubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPostResponseSubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPost
    | None
):
    """Submit Policy

    Args:
        policy_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPostResponseSubmitPolicyApiV1ExtGrcPoliciesPolicyIdSubmitReviewPost
    """

    return (
        await asyncio_detailed(
            policy_id=policy_id,
            client=client,
        )
    ).parsed
