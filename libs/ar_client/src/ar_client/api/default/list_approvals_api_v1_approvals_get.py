from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_approvals_api_v1_approvals_get_response_list_approvals_api_v1_approvals_get import (
    ListApprovalsApiV1ApprovalsGetResponseListApprovalsApiV1ApprovalsGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    *,
    scope: str | Unset = "to_decide",
    status: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    risk_class: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["scope"] = scope

    json_status: None | str | Unset
    if isinstance(status, Unset):
        json_status = UNSET
    else:
        json_status = status
    params["status"] = json_status

    json_agent_id: None | str | Unset
    if isinstance(agent_id, Unset):
        json_agent_id = UNSET
    elif isinstance(agent_id, UUID):
        json_agent_id = str(agent_id)
    else:
        json_agent_id = agent_id
    params["agent_id"] = json_agent_id

    json_risk_class: None | str | Unset
    if isinstance(risk_class, Unset):
        json_risk_class = UNSET
    else:
        json_risk_class = risk_class
    params["risk_class"] = json_risk_class

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/approvals",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListApprovalsApiV1ApprovalsGetResponseListApprovalsApiV1ApprovalsGet
    | None
):
    if response.status_code == 200:
        response_200 = (
            ListApprovalsApiV1ApprovalsGetResponseListApprovalsApiV1ApprovalsGet.from_dict(
                response.json()
            )
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
    HTTPValidationError | ListApprovalsApiV1ApprovalsGetResponseListApprovalsApiV1ApprovalsGet
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
    scope: str | Unset = "to_decide",
    status: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    risk_class: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError | ListApprovalsApiV1ApprovalsGetResponseListApprovalsApiV1ApprovalsGet
]:
    """List Approvals

    Args:
        scope (str | Unset):  Default: 'to_decide'.
        status (None | str | Unset):
        agent_id (None | Unset | UUID):
        risk_class (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListApprovalsApiV1ApprovalsGetResponseListApprovalsApiV1ApprovalsGet]
    """

    kwargs = _get_kwargs(
        scope=scope,
        status=status,
        agent_id=agent_id,
        risk_class=risk_class,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    scope: str | Unset = "to_decide",
    status: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    risk_class: None | str | Unset = UNSET,
) -> (
    HTTPValidationError
    | ListApprovalsApiV1ApprovalsGetResponseListApprovalsApiV1ApprovalsGet
    | None
):
    """List Approvals

    Args:
        scope (str | Unset):  Default: 'to_decide'.
        status (None | str | Unset):
        agent_id (None | Unset | UUID):
        risk_class (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListApprovalsApiV1ApprovalsGetResponseListApprovalsApiV1ApprovalsGet
    """

    return sync_detailed(
        client=client,
        scope=scope,
        status=status,
        agent_id=agent_id,
        risk_class=risk_class,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    scope: str | Unset = "to_decide",
    status: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    risk_class: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError | ListApprovalsApiV1ApprovalsGetResponseListApprovalsApiV1ApprovalsGet
]:
    """List Approvals

    Args:
        scope (str | Unset):  Default: 'to_decide'.
        status (None | str | Unset):
        agent_id (None | Unset | UUID):
        risk_class (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListApprovalsApiV1ApprovalsGetResponseListApprovalsApiV1ApprovalsGet]
    """

    kwargs = _get_kwargs(
        scope=scope,
        status=status,
        agent_id=agent_id,
        risk_class=risk_class,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    scope: str | Unset = "to_decide",
    status: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    risk_class: None | str | Unset = UNSET,
) -> (
    HTTPValidationError
    | ListApprovalsApiV1ApprovalsGetResponseListApprovalsApiV1ApprovalsGet
    | None
):
    """List Approvals

    Args:
        scope (str | Unset):  Default: 'to_decide'.
        status (None | str | Unset):
        agent_id (None | Unset | UUID):
        risk_class (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListApprovalsApiV1ApprovalsGetResponseListApprovalsApiV1ApprovalsGet
    """

    return (
        await asyncio_detailed(
            client=client,
            scope=scope,
            status=status,
            agent_id=agent_id,
            risk_class=risk_class,
        )
    ).parsed
