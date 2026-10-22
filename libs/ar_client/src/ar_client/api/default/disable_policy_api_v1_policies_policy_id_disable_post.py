from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.disable_policy_api_v1_policies_policy_id_disable_post_response_disable_policy_api_v1_policies_policy_id_disable_post import (
    DisablePolicyApiV1PoliciesPolicyIdDisablePostResponseDisablePolicyApiV1PoliciesPolicyIdDisablePost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    policy_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/policies/{policy_id}:disable".format(
            policy_id=quote(str(policy_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DisablePolicyApiV1PoliciesPolicyIdDisablePostResponseDisablePolicyApiV1PoliciesPolicyIdDisablePost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DisablePolicyApiV1PoliciesPolicyIdDisablePostResponseDisablePolicyApiV1PoliciesPolicyIdDisablePost.from_dict(
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
    DisablePolicyApiV1PoliciesPolicyIdDisablePostResponseDisablePolicyApiV1PoliciesPolicyIdDisablePost
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
) -> Response[
    DisablePolicyApiV1PoliciesPolicyIdDisablePostResponseDisablePolicyApiV1PoliciesPolicyIdDisablePost
    | HTTPValidationError
]:
    """Disable Policy

    Args:
        policy_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DisablePolicyApiV1PoliciesPolicyIdDisablePostResponseDisablePolicyApiV1PoliciesPolicyIdDisablePost | HTTPValidationError]
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
    DisablePolicyApiV1PoliciesPolicyIdDisablePostResponseDisablePolicyApiV1PoliciesPolicyIdDisablePost
    | HTTPValidationError
    | None
):
    """Disable Policy

    Args:
        policy_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DisablePolicyApiV1PoliciesPolicyIdDisablePostResponseDisablePolicyApiV1PoliciesPolicyIdDisablePost | HTTPValidationError
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
    DisablePolicyApiV1PoliciesPolicyIdDisablePostResponseDisablePolicyApiV1PoliciesPolicyIdDisablePost
    | HTTPValidationError
]:
    """Disable Policy

    Args:
        policy_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DisablePolicyApiV1PoliciesPolicyIdDisablePostResponseDisablePolicyApiV1PoliciesPolicyIdDisablePost | HTTPValidationError]
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
    DisablePolicyApiV1PoliciesPolicyIdDisablePostResponseDisablePolicyApiV1PoliciesPolicyIdDisablePost
    | HTTPValidationError
    | None
):
    """Disable Policy

    Args:
        policy_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DisablePolicyApiV1PoliciesPolicyIdDisablePostResponseDisablePolicyApiV1PoliciesPolicyIdDisablePost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            policy_id=policy_id,
            client=client,
        )
    ).parsed
