from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_policy_api_v1_policies_policy_id_patch_response_patch_policy_api_v1_policies_policy_id_patch import (
    PatchPolicyApiV1PoliciesPolicyIdPatchResponsePatchPolicyApiV1PoliciesPolicyIdPatch,
)
from ...models.policy_patch import PolicyPatch
from typing import cast
from uuid import UUID


def _get_kwargs(
    policy_id: UUID,
    *,
    body: PolicyPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/policies/{policy_id}".format(
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
    HTTPValidationError
    | PatchPolicyApiV1PoliciesPolicyIdPatchResponsePatchPolicyApiV1PoliciesPolicyIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchPolicyApiV1PoliciesPolicyIdPatchResponsePatchPolicyApiV1PoliciesPolicyIdPatch.from_dict(
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
    | PatchPolicyApiV1PoliciesPolicyIdPatchResponsePatchPolicyApiV1PoliciesPolicyIdPatch
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
    body: PolicyPatch,
) -> Response[
    HTTPValidationError
    | PatchPolicyApiV1PoliciesPolicyIdPatchResponsePatchPolicyApiV1PoliciesPolicyIdPatch
]:
    """Patch Policy

    Args:
        policy_id (UUID):
        body (PolicyPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchPolicyApiV1PoliciesPolicyIdPatchResponsePatchPolicyApiV1PoliciesPolicyIdPatch]
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
    body: PolicyPatch,
) -> (
    HTTPValidationError
    | PatchPolicyApiV1PoliciesPolicyIdPatchResponsePatchPolicyApiV1PoliciesPolicyIdPatch
    | None
):
    """Patch Policy

    Args:
        policy_id (UUID):
        body (PolicyPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchPolicyApiV1PoliciesPolicyIdPatchResponsePatchPolicyApiV1PoliciesPolicyIdPatch
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
    body: PolicyPatch,
) -> Response[
    HTTPValidationError
    | PatchPolicyApiV1PoliciesPolicyIdPatchResponsePatchPolicyApiV1PoliciesPolicyIdPatch
]:
    """Patch Policy

    Args:
        policy_id (UUID):
        body (PolicyPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchPolicyApiV1PoliciesPolicyIdPatchResponsePatchPolicyApiV1PoliciesPolicyIdPatch]
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
    body: PolicyPatch,
) -> (
    HTTPValidationError
    | PatchPolicyApiV1PoliciesPolicyIdPatchResponsePatchPolicyApiV1PoliciesPolicyIdPatch
    | None
):
    """Patch Policy

    Args:
        policy_id (UUID):
        body (PolicyPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchPolicyApiV1PoliciesPolicyIdPatchResponsePatchPolicyApiV1PoliciesPolicyIdPatch
    """

    return (
        await asyncio_detailed(
            policy_id=policy_id,
            client=client,
            body=body,
        )
    ).parsed
