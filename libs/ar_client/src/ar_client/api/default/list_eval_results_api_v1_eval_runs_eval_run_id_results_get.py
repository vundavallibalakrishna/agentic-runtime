from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_eval_results_api_v1_eval_runs_eval_run_id_results_get_response_list_eval_results_api_v1_eval_runs_eval_run_id_results_get import (
    ListEvalResultsApiV1EvalRunsEvalRunIdResultsGetResponseListEvalResultsApiV1EvalRunsEvalRunIdResultsGet,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    eval_run_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/eval-runs/{eval_run_id}/results".format(
            eval_run_id=quote(str(eval_run_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | ListEvalResultsApiV1EvalRunsEvalRunIdResultsGetResponseListEvalResultsApiV1EvalRunsEvalRunIdResultsGet
    | None
):
    if response.status_code == 200:
        response_200 = ListEvalResultsApiV1EvalRunsEvalRunIdResultsGetResponseListEvalResultsApiV1EvalRunsEvalRunIdResultsGet.from_dict(
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
    | ListEvalResultsApiV1EvalRunsEvalRunIdResultsGetResponseListEvalResultsApiV1EvalRunsEvalRunIdResultsGet
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
    HTTPValidationError
    | ListEvalResultsApiV1EvalRunsEvalRunIdResultsGetResponseListEvalResultsApiV1EvalRunsEvalRunIdResultsGet
]:
    """List Eval Results

    Args:
        eval_run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListEvalResultsApiV1EvalRunsEvalRunIdResultsGetResponseListEvalResultsApiV1EvalRunsEvalRunIdResultsGet]
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
    HTTPValidationError
    | ListEvalResultsApiV1EvalRunsEvalRunIdResultsGetResponseListEvalResultsApiV1EvalRunsEvalRunIdResultsGet
    | None
):
    """List Eval Results

    Args:
        eval_run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListEvalResultsApiV1EvalRunsEvalRunIdResultsGetResponseListEvalResultsApiV1EvalRunsEvalRunIdResultsGet
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
    HTTPValidationError
    | ListEvalResultsApiV1EvalRunsEvalRunIdResultsGetResponseListEvalResultsApiV1EvalRunsEvalRunIdResultsGet
]:
    """List Eval Results

    Args:
        eval_run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListEvalResultsApiV1EvalRunsEvalRunIdResultsGetResponseListEvalResultsApiV1EvalRunsEvalRunIdResultsGet]
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
    HTTPValidationError
    | ListEvalResultsApiV1EvalRunsEvalRunIdResultsGetResponseListEvalResultsApiV1EvalRunsEvalRunIdResultsGet
    | None
):
    """List Eval Results

    Args:
        eval_run_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListEvalResultsApiV1EvalRunsEvalRunIdResultsGetResponseListEvalResultsApiV1EvalRunsEvalRunIdResultsGet
    """

    return (
        await asyncio_detailed(
            eval_run_id=eval_run_id,
            client=client,
        )
    ).parsed
