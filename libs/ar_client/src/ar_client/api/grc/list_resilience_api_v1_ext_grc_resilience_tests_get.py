from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_resilience_api_v1_ext_grc_resilience_tests_get_response_list_resilience_api_v1_ext_grc_resilience_tests_get import (
    ListResilienceApiV1ExtGrcResilienceTestsGetResponseListResilienceApiV1ExtGrcResilienceTestsGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/resilience-tests",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ListResilienceApiV1ExtGrcResilienceTestsGetResponseListResilienceApiV1ExtGrcResilienceTestsGet
    | None
):
    if response.status_code == 200:
        response_200 = ListResilienceApiV1ExtGrcResilienceTestsGetResponseListResilienceApiV1ExtGrcResilienceTestsGet.from_dict(
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
    ListResilienceApiV1ExtGrcResilienceTestsGetResponseListResilienceApiV1ExtGrcResilienceTestsGet
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
    ListResilienceApiV1ExtGrcResilienceTestsGetResponseListResilienceApiV1ExtGrcResilienceTestsGet
]:
    """List Resilience

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListResilienceApiV1ExtGrcResilienceTestsGetResponseListResilienceApiV1ExtGrcResilienceTestsGet]
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
    ListResilienceApiV1ExtGrcResilienceTestsGetResponseListResilienceApiV1ExtGrcResilienceTestsGet
    | None
):
    """List Resilience

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListResilienceApiV1ExtGrcResilienceTestsGetResponseListResilienceApiV1ExtGrcResilienceTestsGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ListResilienceApiV1ExtGrcResilienceTestsGetResponseListResilienceApiV1ExtGrcResilienceTestsGet
]:
    """List Resilience

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListResilienceApiV1ExtGrcResilienceTestsGetResponseListResilienceApiV1ExtGrcResilienceTestsGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> (
    ListResilienceApiV1ExtGrcResilienceTestsGetResponseListResilienceApiV1ExtGrcResilienceTestsGet
    | None
):
    """List Resilience

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListResilienceApiV1ExtGrcResilienceTestsGetResponseListResilienceApiV1ExtGrcResilienceTestsGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
