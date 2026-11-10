from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.import_rule_set_route_api_v1_rule_sets_post_response_import_rule_set_route_api_v1_rule_sets_post import (
    ImportRuleSetRouteApiV1RuleSetsPostResponseImportRuleSetRouteApiV1RuleSetsPost,
)
from ...models.rule_set_body import RuleSetBody
from typing import cast


def _get_kwargs(
    *,
    body: RuleSetBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/rule-sets",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ImportRuleSetRouteApiV1RuleSetsPostResponseImportRuleSetRouteApiV1RuleSetsPost
    | None
):
    if response.status_code == 200:
        response_200 = ImportRuleSetRouteApiV1RuleSetsPostResponseImportRuleSetRouteApiV1RuleSetsPost.from_dict(
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
    | ImportRuleSetRouteApiV1RuleSetsPostResponseImportRuleSetRouteApiV1RuleSetsPost
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
    body: RuleSetBody,
) -> Response[
    HTTPValidationError
    | ImportRuleSetRouteApiV1RuleSetsPostResponseImportRuleSetRouteApiV1RuleSetsPost
]:
    """Import Rule Set Route

    Args:
        body (RuleSetBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ImportRuleSetRouteApiV1RuleSetsPostResponseImportRuleSetRouteApiV1RuleSetsPost]
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
    body: RuleSetBody,
) -> (
    HTTPValidationError
    | ImportRuleSetRouteApiV1RuleSetsPostResponseImportRuleSetRouteApiV1RuleSetsPost
    | None
):
    """Import Rule Set Route

    Args:
        body (RuleSetBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ImportRuleSetRouteApiV1RuleSetsPostResponseImportRuleSetRouteApiV1RuleSetsPost
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: RuleSetBody,
) -> Response[
    HTTPValidationError
    | ImportRuleSetRouteApiV1RuleSetsPostResponseImportRuleSetRouteApiV1RuleSetsPost
]:
    """Import Rule Set Route

    Args:
        body (RuleSetBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ImportRuleSetRouteApiV1RuleSetsPostResponseImportRuleSetRouteApiV1RuleSetsPost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: RuleSetBody,
) -> (
    HTTPValidationError
    | ImportRuleSetRouteApiV1RuleSetsPostResponseImportRuleSetRouteApiV1RuleSetsPost
    | None
):
    """Import Rule Set Route

    Args:
        body (RuleSetBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ImportRuleSetRouteApiV1RuleSetsPostResponseImportRuleSetRouteApiV1RuleSetsPost
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
