from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.draft_questionnaire_api_v1_ext_grc_questionnaires_draft_post_body import (
    DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostBody,
)
from ...models.draft_questionnaire_api_v1_ext_grc_questionnaires_draft_post_response_draft_questionnaire_api_v1_ext_grc_questionnaires_draft_post import (
    DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostResponseDraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast


def _get_kwargs(
    *,
    body: DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/questionnaires:draft",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostResponseDraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPost
    | HTTPValidationError
    | None
):
    if response.status_code == 202:
        response_202 = DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostResponseDraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPost.from_dict(
            response.json()
        )

        return response_202

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
    DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostResponseDraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPost
    | HTTPValidationError
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
    body: DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostBody,
) -> Response[
    DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostResponseDraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPost
    | HTTPValidationError
]:
    """Draft Questionnaire

    Args:
        body (DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostResponseDraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostBody,
) -> (
    DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostResponseDraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPost
    | HTTPValidationError
    | None
):
    """Draft Questionnaire

    Args:
        body (DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostResponseDraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPost | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostBody,
) -> Response[
    DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostResponseDraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPost
    | HTTPValidationError
]:
    """Draft Questionnaire

    Args:
        body (DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostResponseDraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostBody,
) -> (
    DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostResponseDraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPost
    | HTTPValidationError
    | None
):
    """Draft Questionnaire

    Args:
        body (DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPostResponseDraftQuestionnaireApiV1ExtGrcQuestionnairesDraftPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
