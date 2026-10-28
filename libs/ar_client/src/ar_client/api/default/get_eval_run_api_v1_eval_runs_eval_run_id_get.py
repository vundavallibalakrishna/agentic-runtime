from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_eval_run_api_v1_eval_runs_eval_run_id_get_response_get_eval_run_api_v1_eval_runs_eval_run_id_get import (
    GetEvalRunApiV1EvalRunsEvalRunIdGetResponseGetEvalRunApiV1EvalRunsEvalRunIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    eval_run_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/eval-runs/{eval_run_id}".format(
            eval_run_id=quote(str(eval_run_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetEvalRunApiV1EvalRunsEvalRunIdGetResponseGetEvalRunApiV1EvalRunsEvalRunIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetEvalRunApiV1EvalRunsEvalRunIdGetResponseGetEvalRunApiV1EvalRunsEvalRunIdGet.from_dict(
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
    GetEvalRunApiV1EvalRunsEvalRunIdGetResponseGetEvalRunApiV1EvalRunsEvalRunIdGet
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    eval_run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetEvalRunApiV1EvalRunsEvalRunIdGetResponseGetEvalRunApiV1EvalRunsEvalRunIdGet
    | HTTPValidationError
]:
    """Get Eval Run

    Args:
        eval_run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetEvalRunApiV1EvalRunsEvalRunIdGetResponseGetEvalRunApiV1EvalRunsEvalRunIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        eval_run_id=eval_run_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    eval_run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetEvalRunApiV1EvalRunsEvalRunIdGetResponseGetEvalRunApiV1EvalRunsEvalRunIdGet
    | HTTPValidationError
    | None
):
    """Get Eval Run

    Args:
        eval_run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetEvalRunApiV1EvalRunsEvalRunIdGetResponseGetEvalRunApiV1EvalRunsEvalRunIdGet | HTTPValidationError
    """

    return sync_detailed(
        eval_run_id=eval_run_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    eval_run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    GetEvalRunApiV1EvalRunsEvalRunIdGetResponseGetEvalRunApiV1EvalRunsEvalRunIdGet
    | HTTPValidationError
]:
    """Get Eval Run

    Args:
        eval_run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetEvalRunApiV1EvalRunsEvalRunIdGetResponseGetEvalRunApiV1EvalRunsEvalRunIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        eval_run_id=eval_run_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    eval_run_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    GetEvalRunApiV1EvalRunsEvalRunIdGetResponseGetEvalRunApiV1EvalRunsEvalRunIdGet
    | HTTPValidationError
    | None
):
    """Get Eval Run

    Args:
        eval_run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetEvalRunApiV1EvalRunsEvalRunIdGetResponseGetEvalRunApiV1EvalRunsEvalRunIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            eval_run_id=eval_run_id,
            client=client,
        )
    ).parsed
