from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.case_body import CaseBody
from ...models.create_eval_case_api_v1_eval_suites_suite_id_cases_post_response_create_eval_case_api_v1_eval_suites_suite_id_cases_post import (
    CreateEvalCaseApiV1EvalSuitesSuiteIdCasesPostResponseCreateEvalCaseApiV1EvalSuitesSuiteIdCasesPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    suite_id: UUID,
    *,
    body: CaseBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/eval-suites/{suite_id}/cases".format(
            suite_id=quote(str(suite_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateEvalCaseApiV1EvalSuitesSuiteIdCasesPostResponseCreateEvalCaseApiV1EvalSuitesSuiteIdCasesPost
    | HTTPValidationError
    | None
):
    if response.status_code == 201:
        response_201 = CreateEvalCaseApiV1EvalSuitesSuiteIdCasesPostResponseCreateEvalCaseApiV1EvalSuitesSuiteIdCasesPost.from_dict(
            response.json()
        )

        return response_201

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
    CreateEvalCaseApiV1EvalSuitesSuiteIdCasesPostResponseCreateEvalCaseApiV1EvalSuitesSuiteIdCasesPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    suite_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CaseBody,
) -> Response[
    CreateEvalCaseApiV1EvalSuitesSuiteIdCasesPostResponseCreateEvalCaseApiV1EvalSuitesSuiteIdCasesPost
    | HTTPValidationError
]:
    """Create Eval Case

    Args:
        suite_id (UUID):
        body (CaseBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateEvalCaseApiV1EvalSuitesSuiteIdCasesPostResponseCreateEvalCaseApiV1EvalSuitesSuiteIdCasesPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        suite_id=suite_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    suite_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CaseBody,
) -> (
    CreateEvalCaseApiV1EvalSuitesSuiteIdCasesPostResponseCreateEvalCaseApiV1EvalSuitesSuiteIdCasesPost
    | HTTPValidationError
    | None
):
    """Create Eval Case

    Args:
        suite_id (UUID):
        body (CaseBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateEvalCaseApiV1EvalSuitesSuiteIdCasesPostResponseCreateEvalCaseApiV1EvalSuitesSuiteIdCasesPost | HTTPValidationError
    """

    return sync_detailed(
        suite_id=suite_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    suite_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CaseBody,
) -> Response[
    CreateEvalCaseApiV1EvalSuitesSuiteIdCasesPostResponseCreateEvalCaseApiV1EvalSuitesSuiteIdCasesPost
    | HTTPValidationError
]:
    """Create Eval Case

    Args:
        suite_id (UUID):
        body (CaseBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateEvalCaseApiV1EvalSuitesSuiteIdCasesPostResponseCreateEvalCaseApiV1EvalSuitesSuiteIdCasesPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        suite_id=suite_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    suite_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CaseBody,
) -> (
    CreateEvalCaseApiV1EvalSuitesSuiteIdCasesPostResponseCreateEvalCaseApiV1EvalSuitesSuiteIdCasesPost
    | HTTPValidationError
    | None
):
    """Create Eval Case

    Args:
        suite_id (UUID):
        body (CaseBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateEvalCaseApiV1EvalSuitesSuiteIdCasesPostResponseCreateEvalCaseApiV1EvalSuitesSuiteIdCasesPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            suite_id=suite_id,
            client=client,
            body=body,
        )
    ).parsed
