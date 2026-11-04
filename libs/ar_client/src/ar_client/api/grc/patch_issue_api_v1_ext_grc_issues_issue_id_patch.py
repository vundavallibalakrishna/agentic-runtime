from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_issue_api_v1_ext_grc_issues_issue_id_patch_body import (
    PatchIssueApiV1ExtGrcIssuesIssueIdPatchBody,
)
from ...models.patch_issue_api_v1_ext_grc_issues_issue_id_patch_response_patch_issue_api_v1_ext_grc_issues_issue_id_patch import (
    PatchIssueApiV1ExtGrcIssuesIssueIdPatchResponsePatchIssueApiV1ExtGrcIssuesIssueIdPatch,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    issue_id: UUID,
    *,
    body: PatchIssueApiV1ExtGrcIssuesIssueIdPatchBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/ext/grc/issues/{issue_id}".format(
            issue_id=quote(str(issue_id), safe=""),
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
    | PatchIssueApiV1ExtGrcIssuesIssueIdPatchResponsePatchIssueApiV1ExtGrcIssuesIssueIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchIssueApiV1ExtGrcIssuesIssueIdPatchResponsePatchIssueApiV1ExtGrcIssuesIssueIdPatch.from_dict(
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
    | PatchIssueApiV1ExtGrcIssuesIssueIdPatchResponsePatchIssueApiV1ExtGrcIssuesIssueIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    issue_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchIssueApiV1ExtGrcIssuesIssueIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchIssueApiV1ExtGrcIssuesIssueIdPatchResponsePatchIssueApiV1ExtGrcIssuesIssueIdPatch
]:
    """Patch Issue

    Args:
        issue_id (UUID):
        body (PatchIssueApiV1ExtGrcIssuesIssueIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchIssueApiV1ExtGrcIssuesIssueIdPatchResponsePatchIssueApiV1ExtGrcIssuesIssueIdPatch]
    """

    kwargs = _get_kwargs(
        issue_id=issue_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    issue_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchIssueApiV1ExtGrcIssuesIssueIdPatchBody,
) -> (
    HTTPValidationError
    | PatchIssueApiV1ExtGrcIssuesIssueIdPatchResponsePatchIssueApiV1ExtGrcIssuesIssueIdPatch
    | None
):
    """Patch Issue

    Args:
        issue_id (UUID):
        body (PatchIssueApiV1ExtGrcIssuesIssueIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchIssueApiV1ExtGrcIssuesIssueIdPatchResponsePatchIssueApiV1ExtGrcIssuesIssueIdPatch
    """

    return sync_detailed(
        issue_id=issue_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    issue_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchIssueApiV1ExtGrcIssuesIssueIdPatchBody,
) -> Response[
    HTTPValidationError
    | PatchIssueApiV1ExtGrcIssuesIssueIdPatchResponsePatchIssueApiV1ExtGrcIssuesIssueIdPatch
]:
    """Patch Issue

    Args:
        issue_id (UUID):
        body (PatchIssueApiV1ExtGrcIssuesIssueIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchIssueApiV1ExtGrcIssuesIssueIdPatchResponsePatchIssueApiV1ExtGrcIssuesIssueIdPatch]
    """

    kwargs = _get_kwargs(
        issue_id=issue_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    issue_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PatchIssueApiV1ExtGrcIssuesIssueIdPatchBody,
) -> (
    HTTPValidationError
    | PatchIssueApiV1ExtGrcIssuesIssueIdPatchResponsePatchIssueApiV1ExtGrcIssuesIssueIdPatch
    | None
):
    """Patch Issue

    Args:
        issue_id (UUID):
        body (PatchIssueApiV1ExtGrcIssuesIssueIdPatchBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchIssueApiV1ExtGrcIssuesIssueIdPatchResponsePatchIssueApiV1ExtGrcIssuesIssueIdPatch
    """

    return (
        await asyncio_detailed(
            issue_id=issue_id,
            client=client,
            body=body,
        )
    ).parsed
