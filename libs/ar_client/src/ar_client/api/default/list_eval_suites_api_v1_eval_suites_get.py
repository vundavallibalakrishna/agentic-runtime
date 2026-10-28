from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_eval_suites_api_v1_eval_suites_get_response_list_eval_suites_api_v1_eval_suites_get import (
    ListEvalSuitesApiV1EvalSuitesGetResponseListEvalSuitesApiV1EvalSuitesGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    *,
    agent_id: None | Unset | UUID = UNSET,
    kind: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_agent_id: None | str | Unset
    if isinstance(agent_id, Unset):
        json_agent_id = UNSET
    elif isinstance(agent_id, UUID):
        json_agent_id = str(agent_id)
    else:
        json_agent_id = agent_id
    params["agent_id"] = json_agent_id

    json_kind: None | str | Unset
    if isinstance(kind, Unset):
        json_kind = UNSET
    else:
        json_kind = kind
    params["kind"] = json_kind

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/eval-suites",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListEvalSuitesApiV1EvalSuitesGetResponseListEvalSuitesApiV1EvalSuitesGet
    | None
):
    if response.status_code == 200:
        response_200 = (
            ListEvalSuitesApiV1EvalSuitesGetResponseListEvalSuitesApiV1EvalSuitesGet.from_dict(
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
    HTTPValidationError | ListEvalSuitesApiV1EvalSuitesGetResponseListEvalSuitesApiV1EvalSuitesGet
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
    agent_id: None | Unset | UUID = UNSET,
    kind: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError | ListEvalSuitesApiV1EvalSuitesGetResponseListEvalSuitesApiV1EvalSuitesGet
]:
    """List Eval Suites

    Args:
        agent_id (None | Unset | UUID):
        kind (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListEvalSuitesApiV1EvalSuitesGetResponseListEvalSuitesApiV1EvalSuitesGet]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        kind=kind,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    agent_id: None | Unset | UUID = UNSET,
    kind: None | str | Unset = UNSET,
) -> (
    HTTPValidationError
    | ListEvalSuitesApiV1EvalSuitesGetResponseListEvalSuitesApiV1EvalSuitesGet
    | None
):
    """List Eval Suites

    Args:
        agent_id (None | Unset | UUID):
        kind (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListEvalSuitesApiV1EvalSuitesGetResponseListEvalSuitesApiV1EvalSuitesGet
    """

    return sync_detailed(
        client=client,
        agent_id=agent_id,
        kind=kind,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    agent_id: None | Unset | UUID = UNSET,
    kind: None | str | Unset = UNSET,
) -> Response[
    HTTPValidationError | ListEvalSuitesApiV1EvalSuitesGetResponseListEvalSuitesApiV1EvalSuitesGet
]:
    """List Eval Suites

    Args:
        agent_id (None | Unset | UUID):
        kind (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListEvalSuitesApiV1EvalSuitesGetResponseListEvalSuitesApiV1EvalSuitesGet]
    """

    kwargs = _get_kwargs(
        agent_id=agent_id,
        kind=kind,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    agent_id: None | Unset | UUID = UNSET,
    kind: None | str | Unset = UNSET,
) -> (
    HTTPValidationError
    | ListEvalSuitesApiV1EvalSuitesGetResponseListEvalSuitesApiV1EvalSuitesGet
    | None
):
    """List Eval Suites

    Args:
        agent_id (None | Unset | UUID):
        kind (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListEvalSuitesApiV1EvalSuitesGetResponseListEvalSuitesApiV1EvalSuitesGet
    """

    return (
        await asyncio_detailed(
            client=client,
            agent_id=agent_id,
            kind=kind,
        )
    ).parsed
