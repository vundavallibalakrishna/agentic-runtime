from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.suite_patch import SuitePatch
from ...models.update_eval_suite_api_v1_eval_suites_suite_id_patch_response_update_eval_suite_api_v1_eval_suites_suite_id_patch import (
    UpdateEvalSuiteApiV1EvalSuitesSuiteIdPatchResponseUpdateEvalSuiteApiV1EvalSuitesSuiteIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    suite_id: UUID,
    *,
    body: SuitePatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/eval-suites/{suite_id}".format(
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
    HTTPValidationError
    | UpdateEvalSuiteApiV1EvalSuitesSuiteIdPatchResponseUpdateEvalSuiteApiV1EvalSuitesSuiteIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = UpdateEvalSuiteApiV1EvalSuitesSuiteIdPatchResponseUpdateEvalSuiteApiV1EvalSuitesSuiteIdPatch.from_dict(
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
    | UpdateEvalSuiteApiV1EvalSuitesSuiteIdPatchResponseUpdateEvalSuiteApiV1EvalSuitesSuiteIdPatch
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
    body: SuitePatch,
) -> Response[
    HTTPValidationError
    | UpdateEvalSuiteApiV1EvalSuitesSuiteIdPatchResponseUpdateEvalSuiteApiV1EvalSuitesSuiteIdPatch
]:
    """Update Eval Suite

    Args:
        suite_id (UUID):
        body (SuitePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UpdateEvalSuiteApiV1EvalSuitesSuiteIdPatchResponseUpdateEvalSuiteApiV1EvalSuitesSuiteIdPatch]
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
    body: SuitePatch,
) -> (
    HTTPValidationError
    | UpdateEvalSuiteApiV1EvalSuitesSuiteIdPatchResponseUpdateEvalSuiteApiV1EvalSuitesSuiteIdPatch
    | None
):
    """Update Eval Suite

    Args:
        suite_id (UUID):
        body (SuitePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UpdateEvalSuiteApiV1EvalSuitesSuiteIdPatchResponseUpdateEvalSuiteApiV1EvalSuitesSuiteIdPatch
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
    body: SuitePatch,
) -> Response[
    HTTPValidationError
    | UpdateEvalSuiteApiV1EvalSuitesSuiteIdPatchResponseUpdateEvalSuiteApiV1EvalSuitesSuiteIdPatch
]:
    """Update Eval Suite

    Args:
        suite_id (UUID):
        body (SuitePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UpdateEvalSuiteApiV1EvalSuitesSuiteIdPatchResponseUpdateEvalSuiteApiV1EvalSuitesSuiteIdPatch]
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
    body: SuitePatch,
) -> (
    HTTPValidationError
    | UpdateEvalSuiteApiV1EvalSuitesSuiteIdPatchResponseUpdateEvalSuiteApiV1EvalSuitesSuiteIdPatch
    | None
):
    """Update Eval Suite

    Args:
        suite_id (UUID):
        body (SuitePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UpdateEvalSuiteApiV1EvalSuitesSuiteIdPatchResponseUpdateEvalSuiteApiV1EvalSuitesSuiteIdPatch
    """

    return (
        await asyncio_detailed(
            suite_id=suite_id,
            client=client,
            body=body,
        )
    ).parsed
