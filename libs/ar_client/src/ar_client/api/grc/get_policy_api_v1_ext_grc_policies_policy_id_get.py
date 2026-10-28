from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_policy_api_v1_ext_grc_policies_policy_id_get_response_get_policy_api_v1_ext_grc_policies_policy_id_get import (
    GetPolicyApiV1ExtGrcPoliciesPolicyIdGetResponseGetPolicyApiV1ExtGrcPoliciesPolicyIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    policy_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/policies/{policy_id}".format(
            policy_id=quote(str(policy_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetPolicyApiV1ExtGrcPoliciesPolicyIdGetResponseGetPolicyApiV1ExtGrcPoliciesPolicyIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetPolicyApiV1ExtGrcPoliciesPolicyIdGetResponseGetPolicyApiV1ExtGrcPoliciesPolicyIdGet.from_dict(
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
    GetPolicyApiV1ExtGrcPoliciesPolicyIdGetResponseGetPolicyApiV1ExtGrcPoliciesPolicyIdGet
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
    GetPolicyApiV1ExtGrcPoliciesPolicyIdGetResponseGetPolicyApiV1ExtGrcPoliciesPolicyIdGet
    | HTTPValidationError
]:
    """Get Policy

    Args:
        policy_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetPolicyApiV1ExtGrcPoliciesPolicyIdGetResponseGetPolicyApiV1ExtGrcPoliciesPolicyIdGet | HTTPValidationError]
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
    GetPolicyApiV1ExtGrcPoliciesPolicyIdGetResponseGetPolicyApiV1ExtGrcPoliciesPolicyIdGet
    | HTTPValidationError
    | None
):
    """Get Policy

    Args:
        policy_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetPolicyApiV1ExtGrcPoliciesPolicyIdGetResponseGetPolicyApiV1ExtGrcPoliciesPolicyIdGet | HTTPValidationError
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
    GetPolicyApiV1ExtGrcPoliciesPolicyIdGetResponseGetPolicyApiV1ExtGrcPoliciesPolicyIdGet
    | HTTPValidationError
]:
    """Get Policy

    Args:
        policy_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetPolicyApiV1ExtGrcPoliciesPolicyIdGetResponseGetPolicyApiV1ExtGrcPoliciesPolicyIdGet | HTTPValidationError]
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
    GetPolicyApiV1ExtGrcPoliciesPolicyIdGetResponseGetPolicyApiV1ExtGrcPoliciesPolicyIdGet
    | HTTPValidationError
    | None
):
    """Get Policy

    Args:
        policy_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetPolicyApiV1ExtGrcPoliciesPolicyIdGetResponseGetPolicyApiV1ExtGrcPoliciesPolicyIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            policy_id=policy_id,
            client=client,
        )
    ).parsed
