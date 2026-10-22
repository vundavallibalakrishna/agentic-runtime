from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.publish_skill_api_v1_skills_skill_id_publish_post_response_publish_skill_api_v1_skills_skill_id_publish_post import (
    PublishSkillApiV1SkillsSkillIdPublishPostResponsePublishSkillApiV1SkillsSkillIdPublishPost,
)
from ...models.skill_publish_body import SkillPublishBody
from typing import cast
from uuid import UUID


def _get_kwargs(
    skill_id: UUID,
    *,
    body: SkillPublishBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/skills/{skill_id}:publish".format(
            skill_id=quote(str(skill_id), safe=""),
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
    | PublishSkillApiV1SkillsSkillIdPublishPostResponsePublishSkillApiV1SkillsSkillIdPublishPost
    | None
):
    if response.status_code == 200:
        response_200 = PublishSkillApiV1SkillsSkillIdPublishPostResponsePublishSkillApiV1SkillsSkillIdPublishPost.from_dict(
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
    | PublishSkillApiV1SkillsSkillIdPublishPostResponsePublishSkillApiV1SkillsSkillIdPublishPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    skill_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SkillPublishBody,
) -> Response[
    HTTPValidationError
    | PublishSkillApiV1SkillsSkillIdPublishPostResponsePublishSkillApiV1SkillsSkillIdPublishPost
]:
    """Publish Skill

    Args:
        skill_id (UUID):
        body (SkillPublishBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PublishSkillApiV1SkillsSkillIdPublishPostResponsePublishSkillApiV1SkillsSkillIdPublishPost]
    """

    kwargs = _get_kwargs(
        skill_id=skill_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    skill_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SkillPublishBody,
) -> (
    HTTPValidationError
    | PublishSkillApiV1SkillsSkillIdPublishPostResponsePublishSkillApiV1SkillsSkillIdPublishPost
    | None
):
    """Publish Skill

    Args:
        skill_id (UUID):
        body (SkillPublishBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PublishSkillApiV1SkillsSkillIdPublishPostResponsePublishSkillApiV1SkillsSkillIdPublishPost
    """

    return sync_detailed(
        skill_id=skill_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    skill_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SkillPublishBody,
) -> Response[
    HTTPValidationError
    | PublishSkillApiV1SkillsSkillIdPublishPostResponsePublishSkillApiV1SkillsSkillIdPublishPost
]:
    """Publish Skill

    Args:
        skill_id (UUID):
        body (SkillPublishBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PublishSkillApiV1SkillsSkillIdPublishPostResponsePublishSkillApiV1SkillsSkillIdPublishPost]
    """

    kwargs = _get_kwargs(
        skill_id=skill_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    skill_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SkillPublishBody,
) -> (
    HTTPValidationError
    | PublishSkillApiV1SkillsSkillIdPublishPostResponsePublishSkillApiV1SkillsSkillIdPublishPost
    | None
):
    """Publish Skill

    Args:
        skill_id (UUID):
        body (SkillPublishBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PublishSkillApiV1SkillsSkillIdPublishPostResponsePublishSkillApiV1SkillsSkillIdPublishPost
    """

    return (
        await asyncio_detailed(
            skill_id=skill_id,
            client=client,
            body=body,
        )
    ).parsed
