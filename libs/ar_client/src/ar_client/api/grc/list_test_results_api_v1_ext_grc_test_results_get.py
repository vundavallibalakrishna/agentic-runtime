from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_test_results_api_v1_ext_grc_test_results_get_response_list_test_results_api_v1_ext_grc_test_results_get import (
    ListTestResultsApiV1ExtGrcTestResultsGetResponseListTestResultsApiV1ExtGrcTestResultsGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/test-results",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ListTestResultsApiV1ExtGrcTestResultsGetResponseListTestResultsApiV1ExtGrcTestResultsGet | None
):
    if response.status_code == 200:
        response_200 = ListTestResultsApiV1ExtGrcTestResultsGetResponseListTestResultsApiV1ExtGrcTestResultsGet.from_dict(
            response.json()
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    ListTestResultsApiV1ExtGrcTestResultsGetResponseListTestResultsApiV1ExtGrcTestResultsGet
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
) -> Response[
    ListTestResultsApiV1ExtGrcTestResultsGetResponseListTestResultsApiV1ExtGrcTestResultsGet
]:
    """List Test Results

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListTestResultsApiV1ExtGrcTestResultsGetResponseListTestResultsApiV1ExtGrcTestResultsGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> (
    ListTestResultsApiV1ExtGrcTestResultsGetResponseListTestResultsApiV1ExtGrcTestResultsGet | None
):
    """List Test Results

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListTestResultsApiV1ExtGrcTestResultsGetResponseListTestResultsApiV1ExtGrcTestResultsGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ListTestResultsApiV1ExtGrcTestResultsGetResponseListTestResultsApiV1ExtGrcTestResultsGet
]:
    """List Test Results

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListTestResultsApiV1ExtGrcTestResultsGetResponseListTestResultsApiV1ExtGrcTestResultsGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> (
    ListTestResultsApiV1ExtGrcTestResultsGetResponseListTestResultsApiV1ExtGrcTestResultsGet | None
):
    """List Test Results

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListTestResultsApiV1ExtGrcTestResultsGetResponseListTestResultsApiV1ExtGrcTestResultsGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
