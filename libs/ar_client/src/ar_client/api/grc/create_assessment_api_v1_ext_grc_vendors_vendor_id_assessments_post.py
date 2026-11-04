from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.create_assessment_api_v1_ext_grc_vendors_vendor_id_assessments_post_body import (
    CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostBody,
)
from ...models.create_assessment_api_v1_ext_grc_vendors_vendor_id_assessments_post_response_create_assessment_api_v1_ext_grc_vendors_vendor_id_assessments_post import (
    CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostResponseCreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    vendor_id: UUID,
    *,
    body: CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ext/grc/vendors/{vendor_id}/assessments".format(
            vendor_id=quote(str(vendor_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostResponseCreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostResponseCreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPost.from_dict(
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
    CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostResponseCreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    vendor_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostBody,
) -> Response[
    CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostResponseCreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPost
    | HTTPValidationError
]:
    """Create Assessment

    Args:
        vendor_id (UUID):
        body (CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostResponseCreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        vendor_id=vendor_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    vendor_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostBody,
) -> (
    CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostResponseCreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPost
    | HTTPValidationError
    | None
):
    """Create Assessment

    Args:
        vendor_id (UUID):
        body (CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostResponseCreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPost | HTTPValidationError
    """

    return sync_detailed(
        vendor_id=vendor_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    vendor_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostBody,
) -> Response[
    CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostResponseCreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPost
    | HTTPValidationError
]:
    """Create Assessment

    Args:
        vendor_id (UUID):
        body (CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostResponseCreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        vendor_id=vendor_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    vendor_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostBody,
) -> (
    CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostResponseCreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPost
    | HTTPValidationError
    | None
):
    """Create Assessment

    Args:
        vendor_id (UUID):
        body (CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPostResponseCreateAssessmentApiV1ExtGrcVendorsVendorIdAssessmentsPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            vendor_id=vendor_id,
            client=client,
            body=body,
        )
    ).parsed
