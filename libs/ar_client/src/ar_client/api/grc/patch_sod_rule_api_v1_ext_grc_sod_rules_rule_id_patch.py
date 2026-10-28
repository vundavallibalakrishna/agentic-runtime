from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_sod_rule_api_v1_ext_grc_sod_rules_rule_id_patch_body import (
    PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchBody,
)
from ...models.patch_sod_rule_api_v1_ext_grc_sod_rules_rule_id_patch_response_patch_sod_rule_api_v1_ext_grc_sod_rules_rule_id_patch import (
    PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchResponsePatchSodRuleApiV1ExtGrcSodRulesRuleIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    rule_id: UUID,
    *,
    body: PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/ext/grc/sod-rules/{rule_id}".format(
            rule_id=quote(str(rule_id), safe=""),
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
    | PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchResponsePatchSodRuleApiV1ExtGrcSodRulesRuleIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchResponsePatchSodRuleApiV1ExtGrcSodRulesRuleIdPatch.from_dict(
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
    | PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchResponsePatchSodRuleApiV1ExtGrcSodRulesRuleIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    rule_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchResponsePatchSodRuleApiV1ExtGrcSodRulesRuleIdPatch
]:
    """Patch Sod Rule

    Args:
        rule_id (UUID):
        body (PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchResponsePatchSodRuleApiV1ExtGrcSodRulesRuleIdPatch]
    """

    kwargs = _get_kwargs(
        rule_id=rule_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    rule_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchBody,
) -> (
    HTTPValidationError
    | PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchResponsePatchSodRuleApiV1ExtGrcSodRulesRuleIdPatch
    | None
):
    """Patch Sod Rule

    Args:
        rule_id (UUID):
        body (PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchResponsePatchSodRuleApiV1ExtGrcSodRulesRuleIdPatch
    """

    return sync_detailed(
        rule_id=rule_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    rule_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchResponsePatchSodRuleApiV1ExtGrcSodRulesRuleIdPatch
]:
    """Patch Sod Rule

    Args:
        rule_id (UUID):
        body (PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchResponsePatchSodRuleApiV1ExtGrcSodRulesRuleIdPatch]
    """

    kwargs = _get_kwargs(
        rule_id=rule_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    rule_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchBody,
) -> (
    HTTPValidationError
    | PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchResponsePatchSodRuleApiV1ExtGrcSodRulesRuleIdPatch
    | None
):
    """Patch Sod Rule

    Args:
        rule_id (UUID):
        body (PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchSodRuleApiV1ExtGrcSodRulesRuleIdPatchResponsePatchSodRuleApiV1ExtGrcSodRulesRuleIdPatch
    """

    return (
        await asyncio_detailed(
            rule_id=rule_id,
            client=client,
            body=body,
        )
    ).parsed
