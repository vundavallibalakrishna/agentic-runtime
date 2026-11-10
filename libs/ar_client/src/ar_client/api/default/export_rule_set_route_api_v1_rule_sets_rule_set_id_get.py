from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.export_rule_set_route_api_v1_rule_sets_rule_set_id_get_response_export_rule_set_route_api_v1_rule_sets_rule_set_id_get import (
    ExportRuleSetRouteApiV1RuleSetsRuleSetIdGetResponseExportRuleSetRouteApiV1RuleSetsRuleSetIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Unset
from typing import cast


def _get_kwargs(
    rule_set_id: str,
    *,
    version: str | Unset = "",
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["version"] = version

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/rule-sets/{rule_set_id}".format(
            rule_set_id=quote(str(rule_set_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ExportRuleSetRouteApiV1RuleSetsRuleSetIdGetResponseExportRuleSetRouteApiV1RuleSetsRuleSetIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = ExportRuleSetRouteApiV1RuleSetsRuleSetIdGetResponseExportRuleSetRouteApiV1RuleSetsRuleSetIdGet.from_dict(
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
    ExportRuleSetRouteApiV1RuleSetsRuleSetIdGetResponseExportRuleSetRouteApiV1RuleSetsRuleSetIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    rule_set_id: str,
    *,
    client: AuthenticatedClient | Client,
    version: str | Unset = "",
) -> Response[
    ExportRuleSetRouteApiV1RuleSetsRuleSetIdGetResponseExportRuleSetRouteApiV1RuleSetsRuleSetIdGet
    | HTTPValidationError
]:
    """Export Rule Set Route

    Args:
        rule_set_id (str):
        version (str | Unset):  Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ExportRuleSetRouteApiV1RuleSetsRuleSetIdGetResponseExportRuleSetRouteApiV1RuleSetsRuleSetIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        rule_set_id=rule_set_id,
        version=version,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    rule_set_id: str,
    *,
    client: AuthenticatedClient | Client,
    version: str | Unset = "",
) -> (
    ExportRuleSetRouteApiV1RuleSetsRuleSetIdGetResponseExportRuleSetRouteApiV1RuleSetsRuleSetIdGet
    | HTTPValidationError
    | None
):
    """Export Rule Set Route

    Args:
        rule_set_id (str):
        version (str | Unset):  Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ExportRuleSetRouteApiV1RuleSetsRuleSetIdGetResponseExportRuleSetRouteApiV1RuleSetsRuleSetIdGet | HTTPValidationError
    """

    return sync_detailed(
        rule_set_id=rule_set_id,
        client=client,
        version=version,
    ).parsed


async def asyncio_detailed(
    rule_set_id: str,
    *,
    client: AuthenticatedClient | Client,
    version: str | Unset = "",
) -> Response[
    ExportRuleSetRouteApiV1RuleSetsRuleSetIdGetResponseExportRuleSetRouteApiV1RuleSetsRuleSetIdGet
    | HTTPValidationError
]:
    """Export Rule Set Route

    Args:
        rule_set_id (str):
        version (str | Unset):  Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ExportRuleSetRouteApiV1RuleSetsRuleSetIdGetResponseExportRuleSetRouteApiV1RuleSetsRuleSetIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        rule_set_id=rule_set_id,
        version=version,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    rule_set_id: str,
    *,
    client: AuthenticatedClient | Client,
    version: str | Unset = "",
) -> (
    ExportRuleSetRouteApiV1RuleSetsRuleSetIdGetResponseExportRuleSetRouteApiV1RuleSetsRuleSetIdGet
    | HTTPValidationError
    | None
):
    """Export Rule Set Route

    Args:
        rule_set_id (str):
        version (str | Unset):  Default: ''.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ExportRuleSetRouteApiV1RuleSetsRuleSetIdGetResponseExportRuleSetRouteApiV1RuleSetsRuleSetIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            rule_set_id=rule_set_id,
            client=client,
            version=version,
        )
    ).parsed
