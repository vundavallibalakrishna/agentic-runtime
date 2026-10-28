from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.observability_overview_api_v1_observability_overview_get_response_observability_overview_api_v1_observability_overview_get import (
    ObservabilityOverviewApiV1ObservabilityOverviewGetResponseObservabilityOverviewApiV1ObservabilityOverviewGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    *,
    from_: None | str | Unset = UNSET,
    to: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_from_: None | str | Unset
    if isinstance(from_, Unset):
        json_from_ = UNSET
    else:
        json_from_ = from_
    params["from"] = json_from_

    json_to: None | str | Unset
    if isinstance(to, Unset):
        json_to = UNSET
    else:
        json_to = to
    params["to"] = json_to

    json_agent_id: None | str | Unset
    if isinstance(agent_id, Unset):
        json_agent_id = UNSET
    elif isinstance(agent_id, UUID):
        json_agent_id = str(agent_id)
    else:
        json_agent_id = agent_id
    params["agent_id"] = json_agent_id

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/observability/overview",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ObservabilityOverviewApiV1ObservabilityOverviewGetResponseObservabilityOverviewApiV1ObservabilityOverviewGet
    | None
):
    if response.status_code == 200:
        response_200 = ObservabilityOverviewApiV1ObservabilityOverviewGetResponseObservabilityOverviewApiV1ObservabilityOverviewGet.from_dict(
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
    | ObservabilityOverviewApiV1ObservabilityOverviewGetResponseObservabilityOverviewApiV1ObservabilityOverviewGet
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
    from_: None | str | Unset = UNSET,
    to: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
) -> Response[
    HTTPValidationError
    | ObservabilityOverviewApiV1ObservabilityOverviewGetResponseObservabilityOverviewApiV1ObservabilityOverviewGet
]:
    """Observability Overview

    Args:
        from_ (None | str | Unset):
        to (None | str | Unset):
        agent_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ObservabilityOverviewApiV1ObservabilityOverviewGetResponseObservabilityOverviewApiV1ObservabilityOverviewGet]
    """

    kwargs = _get_kwargs(
        from_=from_,
        to=to,
        agent_id=agent_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    from_: None | str | Unset = UNSET,
    to: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
) -> (
    HTTPValidationError
    | ObservabilityOverviewApiV1ObservabilityOverviewGetResponseObservabilityOverviewApiV1ObservabilityOverviewGet
    | None
):
    """Observability Overview

    Args:
        from_ (None | str | Unset):
        to (None | str | Unset):
        agent_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ObservabilityOverviewApiV1ObservabilityOverviewGetResponseObservabilityOverviewApiV1ObservabilityOverviewGet
    """

    return sync_detailed(
        client=client,
        from_=from_,
        to=to,
        agent_id=agent_id,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    from_: None | str | Unset = UNSET,
    to: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
) -> Response[
    HTTPValidationError
    | ObservabilityOverviewApiV1ObservabilityOverviewGetResponseObservabilityOverviewApiV1ObservabilityOverviewGet
]:
    """Observability Overview

    Args:
        from_ (None | str | Unset):
        to (None | str | Unset):
        agent_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ObservabilityOverviewApiV1ObservabilityOverviewGetResponseObservabilityOverviewApiV1ObservabilityOverviewGet]
    """

    kwargs = _get_kwargs(
        from_=from_,
        to=to,
        agent_id=agent_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    from_: None | str | Unset = UNSET,
    to: None | str | Unset = UNSET,
    agent_id: None | Unset | UUID = UNSET,
) -> (
    HTTPValidationError
    | ObservabilityOverviewApiV1ObservabilityOverviewGetResponseObservabilityOverviewApiV1ObservabilityOverviewGet
    | None
):
    """Observability Overview

    Args:
        from_ (None | str | Unset):
        to (None | str | Unset):
        agent_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ObservabilityOverviewApiV1ObservabilityOverviewGetResponseObservabilityOverviewApiV1ObservabilityOverviewGet
    """

    return (
        await asyncio_detailed(
            client=client,
            from_=from_,
            to=to,
            agent_id=agent_id,
        )
    ).parsed
