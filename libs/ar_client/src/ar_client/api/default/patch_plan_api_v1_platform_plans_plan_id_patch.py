from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_plan_api_v1_platform_plans_plan_id_patch_response_patch_plan_api_v1_platform_plans_plan_id_patch import PatchPlanApiV1PlatformPlansPlanIdPatchResponsePatchPlanApiV1PlatformPlansPlanIdPatch
from ...models.plan_body import PlanBody
from typing import cast
from uuid import UUID



def _get_kwargs(
    plan_id: UUID,
    *,
    body: PlanBody,

) -> dict[str, Any]:
    headers: dict[str, Any] = {}


    

    

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/platform/plans/{plan_id}".format(plan_id=quote(str(plan_id), safe=""),),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | PatchPlanApiV1PlatformPlansPlanIdPatchResponsePatchPlanApiV1PlatformPlansPlanIdPatch | None:
    if response.status_code == 200:
        response_200 = PatchPlanApiV1PlatformPlansPlanIdPatchResponsePatchPlanApiV1PlatformPlansPlanIdPatch.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | PatchPlanApiV1PlatformPlansPlanIdPatchResponsePatchPlanApiV1PlatformPlansPlanIdPatch]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    plan_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PlanBody,

) -> Response[HTTPValidationError | PatchPlanApiV1PlatformPlansPlanIdPatchResponsePatchPlanApiV1PlatformPlansPlanIdPatch]:
    """ Patch Plan

    Args:
        plan_id (UUID):
        body (PlanBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchPlanApiV1PlatformPlansPlanIdPatchResponsePatchPlanApiV1PlatformPlansPlanIdPatch]
     """


    kwargs = _get_kwargs(
        plan_id=plan_id,
body=body,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    plan_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PlanBody,

) -> HTTPValidationError | PatchPlanApiV1PlatformPlansPlanIdPatchResponsePatchPlanApiV1PlatformPlansPlanIdPatch | None:
    """ Patch Plan

    Args:
        plan_id (UUID):
        body (PlanBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchPlanApiV1PlatformPlansPlanIdPatchResponsePatchPlanApiV1PlatformPlansPlanIdPatch
     """


    return sync_detailed(
        plan_id=plan_id,
client=client,
body=body,

    ).parsed

async def asyncio_detailed(
    plan_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PlanBody,

) -> Response[HTTPValidationError | PatchPlanApiV1PlatformPlansPlanIdPatchResponsePatchPlanApiV1PlatformPlansPlanIdPatch]:
    """ Patch Plan

    Args:
        plan_id (UUID):
        body (PlanBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchPlanApiV1PlatformPlansPlanIdPatchResponsePatchPlanApiV1PlatformPlansPlanIdPatch]
     """


    kwargs = _get_kwargs(
        plan_id=plan_id,
body=body,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    plan_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PlanBody,

) -> HTTPValidationError | PatchPlanApiV1PlatformPlansPlanIdPatchResponsePatchPlanApiV1PlatformPlansPlanIdPatch | None:
    """ Patch Plan

    Args:
        plan_id (UUID):
        body (PlanBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchPlanApiV1PlatformPlansPlanIdPatchResponsePatchPlanApiV1PlatformPlansPlanIdPatch
     """


    return (await asyncio_detailed(
        plan_id=plan_id,
client=client,
body=body,

    )).parsed
