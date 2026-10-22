from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.usage_summary_api_v1_usage_summary_get_response_usage_summary_api_v1_usage_summary_get import (
    UsageSummaryApiV1UsageSummaryGetResponseUsageSummaryApiV1UsageSummaryGet,
)
from ...types import UNSET, Unset
from typing import cast


def _get_kwargs(
    *,
    group_by: str | Unset = "day",
    from_: None | str | Unset = UNSET,
    to: None | str | Unset = UNSET,
    metric: None | str | Unset = UNSET,
    agent_id: None | str | Unset = UNSET,
    user_id: None | str | Unset = UNSET,
    team_id: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["group_by"] = group_by

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

    json_metric: None | str | Unset
    if isinstance(metric, Unset):
        json_metric = UNSET
    else:
        json_metric = metric
    params["metric"] = json_metric

    json_agent_id: None | str | Unset
    if isinstance(agent_id, Unset):
        json_agent_id = UNSET
    else:
        json_agent_id = agent_id
    params["agent_id"] = json_agent_id

    json_user_id: None | str | Unset
    if isinstance(user_id, Unset):
        json_user_id = UNSET
    else:
        json_user_id = user_id
    params["user_id"] = json_user_id

    json_team_id: None | str | Unset
    if isinstance(team_id, Unset):
        json_team_id = UNSET
    else:
        json_team_id = team_id
    params["team_id"] = json_team_id

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/usage/summary",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | UsageSummaryApiV1UsageSummaryGetResponseUsageSummaryApiV1UsageSummaryGet
    | None
):
    if response.status_code == 200:
        response_200 = (
            UsageSummaryApiV1UsageSummaryGetResponseUsageSummaryApiV1UsageSummaryGet.from_dict(
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
    HTTPValidationError | UsageSummaryApiV1UsageSummaryGetResponseUsageSummaryApiV1UsageSummaryGet
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
    group_by: str | Unset = "day",
    from_: None | str | Unset = UNSET,
    to: None | str | Unset = UNSET,
    metric: None | str | Unset = UNSET,
    agent_id: None | str | Unset = UNSET,
    user_id: None | str | Unset = UNSET,
    team_id: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError | UsageSummaryApiV1UsageSummaryGetResponseUsageSummaryApiV1UsageSummaryGet
]:
    """Usage Summary

    Args:
        group_by (str | Unset):  Default: 'day'.
        from_ (None | str | Unset):
        to (None | str | Unset):
        metric (None | str | Unset):
        agent_id (None | str | Unset):
        user_id (None | str | Unset):
        team_id (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UsageSummaryApiV1UsageSummaryGetResponseUsageSummaryApiV1UsageSummaryGet]
    """

    kwargs = _get_kwargs(
        group_by=group_by,
        from_=from_,
        to=to,
        metric=metric,
        agent_id=agent_id,
        user_id=user_id,
        team_id=team_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    group_by: str | Unset = "day",
    from_: None | str | Unset = UNSET,
    to: None | str | Unset = UNSET,
    metric: None | str | Unset = UNSET,
    agent_id: None | str | Unset = UNSET,
    user_id: None | str | Unset = UNSET,
    team_id: None | str | Unset = UNSET,
) -> (
    HTTPValidationError
    | UsageSummaryApiV1UsageSummaryGetResponseUsageSummaryApiV1UsageSummaryGet
    | None
):
    """Usage Summary

    Args:
        group_by (str | Unset):  Default: 'day'.
        from_ (None | str | Unset):
        to (None | str | Unset):
        metric (None | str | Unset):
        agent_id (None | str | Unset):
        user_id (None | str | Unset):
        team_id (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UsageSummaryApiV1UsageSummaryGetResponseUsageSummaryApiV1UsageSummaryGet
    """

    return sync_detailed(
        client=client,
        group_by=group_by,
        from_=from_,
        to=to,
        metric=metric,
        agent_id=agent_id,
        user_id=user_id,
        team_id=team_id,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    group_by: str | Unset = "day",
    from_: None | str | Unset = UNSET,
    to: None | str | Unset = UNSET,
    metric: None | str | Unset = UNSET,
    agent_id: None | str | Unset = UNSET,
    user_id: None | str | Unset = UNSET,
    team_id: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError | UsageSummaryApiV1UsageSummaryGetResponseUsageSummaryApiV1UsageSummaryGet
]:
    """Usage Summary

    Args:
        group_by (str | Unset):  Default: 'day'.
        from_ (None | str | Unset):
        to (None | str | Unset):
        metric (None | str | Unset):
        agent_id (None | str | Unset):
        user_id (None | str | Unset):
        team_id (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UsageSummaryApiV1UsageSummaryGetResponseUsageSummaryApiV1UsageSummaryGet]
    """

    kwargs = _get_kwargs(
        group_by=group_by,
        from_=from_,
        to=to,
        metric=metric,
        agent_id=agent_id,
        user_id=user_id,
        team_id=team_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    group_by: str | Unset = "day",
    from_: None | str | Unset = UNSET,
    to: None | str | Unset = UNSET,
    metric: None | str | Unset = UNSET,
    agent_id: None | str | Unset = UNSET,
    user_id: None | str | Unset = UNSET,
    team_id: None | str | Unset = UNSET,
) -> (
    HTTPValidationError
    | UsageSummaryApiV1UsageSummaryGetResponseUsageSummaryApiV1UsageSummaryGet
    | None
):
    """Usage Summary

    Args:
        group_by (str | Unset):  Default: 'day'.
        from_ (None | str | Unset):
        to (None | str | Unset):
        metric (None | str | Unset):
        agent_id (None | str | Unset):
        user_id (None | str | Unset):
        team_id (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UsageSummaryApiV1UsageSummaryGetResponseUsageSummaryApiV1UsageSummaryGet
    """

    return (
        await asyncio_detailed(
            client=client,
            group_by=group_by,
            from_=from_,
            to=to,
            metric=metric,
            agent_id=agent_id,
            user_id=user_id,
            team_id=team_id,
        )
    ).parsed
