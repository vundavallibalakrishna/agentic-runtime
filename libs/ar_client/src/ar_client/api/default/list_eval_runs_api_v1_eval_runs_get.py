from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_eval_runs_api_v1_eval_runs_get_response_list_eval_runs_api_v1_eval_runs_get import (
    ListEvalRunsApiV1EvalRunsGetResponseListEvalRunsApiV1EvalRunsGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    *,
    suite_id: None | Unset | UUID = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_suite_id: None | str | Unset
    if isinstance(suite_id, Unset):
        json_suite_id = UNSET
    elif isinstance(suite_id, UUID):
        json_suite_id = str(suite_id)
    else:
        json_suite_id = suite_id
    params["suite_id"] = json_suite_id

    json_agent_id: None | str | Unset
    if isinstance(agent_id, Unset):
        json_agent_id = UNSET
    elif isinstance(agent_id, UUID):
        json_agent_id = str(agent_id)
    else:
        json_agent_id = agent_id
    params["agent_id"] = json_agent_id

    json_status: None | str | Unset
    if isinstance(status, Unset):
        json_status = UNSET
    else:
        json_status = status
    params["status"] = json_status

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/eval-runs",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ListEvalRunsApiV1EvalRunsGetResponseListEvalRunsApiV1EvalRunsGet | None:
    if response.status_code == 200:
        response_200 = ListEvalRunsApiV1EvalRunsGetResponseListEvalRunsApiV1EvalRunsGet.from_dict(
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
    HTTPValidationError | ListEvalRunsApiV1EvalRunsGetResponseListEvalRunsApiV1EvalRunsGet
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
    suite_id: None | Unset | UUID = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError | ListEvalRunsApiV1EvalRunsGetResponseListEvalRunsApiV1EvalRunsGet
]:
    """List Eval Runs

    Args:
        suite_id (None | Unset | UUID):
        agent_id (None | Unset | UUID):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListEvalRunsApiV1EvalRunsGetResponseListEvalRunsApiV1EvalRunsGet]
    """

    kwargs = _get_kwargs(
        suite_id=suite_id,
        agent_id=agent_id,
        status=status,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    suite_id: None | Unset | UUID = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
) -> HTTPValidationError | ListEvalRunsApiV1EvalRunsGetResponseListEvalRunsApiV1EvalRunsGet | None:
    """List Eval Runs

    Args:
        suite_id (None | Unset | UUID):
        agent_id (None | Unset | UUID):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListEvalRunsApiV1EvalRunsGetResponseListEvalRunsApiV1EvalRunsGet
    """

    return sync_detailed(
        client=client,
        suite_id=suite_id,
        agent_id=agent_id,
        status=status,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    suite_id: None | Unset | UUID = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError | ListEvalRunsApiV1EvalRunsGetResponseListEvalRunsApiV1EvalRunsGet
]:
    """List Eval Runs

    Args:
        suite_id (None | Unset | UUID):
        agent_id (None | Unset | UUID):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListEvalRunsApiV1EvalRunsGetResponseListEvalRunsApiV1EvalRunsGet]
    """

    kwargs = _get_kwargs(
        suite_id=suite_id,
        agent_id=agent_id,
        status=status,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    suite_id: None | Unset | UUID = UNSET,
    agent_id: None | Unset | UUID = UNSET,
    status: None | str | Unset = UNSET,
) -> HTTPValidationError | ListEvalRunsApiV1EvalRunsGetResponseListEvalRunsApiV1EvalRunsGet | None:
    """List Eval Runs

    Args:
        suite_id (None | Unset | UUID):
        agent_id (None | Unset | UUID):
        status (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListEvalRunsApiV1EvalRunsGetResponseListEvalRunsApiV1EvalRunsGet
    """

    return (
        await asyncio_detailed(
            client=client,
            suite_id=suite_id,
            agent_id=agent_id,
            status=status,
        )
    ).parsed
