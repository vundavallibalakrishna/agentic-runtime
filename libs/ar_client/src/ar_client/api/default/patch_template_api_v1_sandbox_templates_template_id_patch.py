from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_template_api_v1_sandbox_templates_template_id_patch_response_patch_template_api_v1_sandbox_templates_template_id_patch import (
    PatchTemplateApiV1SandboxTemplatesTemplateIdPatchResponsePatchTemplateApiV1SandboxTemplatesTemplateIdPatch,
)
from ...models.template_patch import TemplatePatch
from typing import cast
from uuid import UUID


def _get_kwargs(
    template_id: UUID,
    *,
    body: TemplatePatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/sandbox-templates/{template_id}".format(
            template_id=quote(str(template_id), safe=""),
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
    | PatchTemplateApiV1SandboxTemplatesTemplateIdPatchResponsePatchTemplateApiV1SandboxTemplatesTemplateIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = PatchTemplateApiV1SandboxTemplatesTemplateIdPatchResponsePatchTemplateApiV1SandboxTemplatesTemplateIdPatch.from_dict(
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
    | PatchTemplateApiV1SandboxTemplatesTemplateIdPatchResponsePatchTemplateApiV1SandboxTemplatesTemplateIdPatch
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    template_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: TemplatePatch,
) -> Response[
    HTTPValidationError
    | PatchTemplateApiV1SandboxTemplatesTemplateIdPatchResponsePatchTemplateApiV1SandboxTemplatesTemplateIdPatch
]:
    """Patch Template

    Args:
        template_id (UUID):
        body (TemplatePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchTemplateApiV1SandboxTemplatesTemplateIdPatchResponsePatchTemplateApiV1SandboxTemplatesTemplateIdPatch]
    """

    kwargs = _get_kwargs(
        template_id=template_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    template_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: TemplatePatch,
) -> (
    HTTPValidationError
    | PatchTemplateApiV1SandboxTemplatesTemplateIdPatchResponsePatchTemplateApiV1SandboxTemplatesTemplateIdPatch
    | None
):
    """Patch Template

    Args:
        template_id (UUID):
        body (TemplatePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchTemplateApiV1SandboxTemplatesTemplateIdPatchResponsePatchTemplateApiV1SandboxTemplatesTemplateIdPatch
    """

    return sync_detailed(
        template_id=template_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    template_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: TemplatePatch,
) -> Response[
    HTTPValidationError
    | PatchTemplateApiV1SandboxTemplatesTemplateIdPatchResponsePatchTemplateApiV1SandboxTemplatesTemplateIdPatch
]:
    """Patch Template

    Args:
        template_id (UUID):
        body (TemplatePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchTemplateApiV1SandboxTemplatesTemplateIdPatchResponsePatchTemplateApiV1SandboxTemplatesTemplateIdPatch]
    """

    kwargs = _get_kwargs(
        template_id=template_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    template_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: TemplatePatch,
) -> (
    HTTPValidationError
    | PatchTemplateApiV1SandboxTemplatesTemplateIdPatchResponsePatchTemplateApiV1SandboxTemplatesTemplateIdPatch
    | None
):
    """Patch Template

    Args:
        template_id (UUID):
        body (TemplatePatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchTemplateApiV1SandboxTemplatesTemplateIdPatchResponsePatchTemplateApiV1SandboxTemplatesTemplateIdPatch
    """

    return (
        await asyncio_detailed(
            template_id=template_id,
            client=client,
            body=body,
        )
    ).parsed
