from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.list_findings_api_v1_ext_grc_findings_get_response_list_findings_api_v1_ext_grc_findings_get import (
    ListFindingsApiV1ExtGrcFindingsGetResponseListFindingsApiV1ExtGrcFindingsGet,
)
from typing import cast


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/ext/grc/findings",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ListFindingsApiV1ExtGrcFindingsGetResponseListFindingsApiV1ExtGrcFindingsGet | None:
    if response.status_code == 200:
        response_200 = (
            ListFindingsApiV1ExtGrcFindingsGetResponseListFindingsApiV1ExtGrcFindingsGet.from_dict(
                response.json()
            )
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ListFindingsApiV1ExtGrcFindingsGetResponseListFindingsApiV1ExtGrcFindingsGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListFindingsApiV1ExtGrcFindingsGetResponseListFindingsApiV1ExtGrcFindingsGet]:
    """List Findings

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListFindingsApiV1ExtGrcFindingsGetResponseListFindingsApiV1ExtGrcFindingsGet]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> ListFindingsApiV1ExtGrcFindingsGetResponseListFindingsApiV1ExtGrcFindingsGet | None:
    """List Findings

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListFindingsApiV1ExtGrcFindingsGetResponseListFindingsApiV1ExtGrcFindingsGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ListFindingsApiV1ExtGrcFindingsGetResponseListFindingsApiV1ExtGrcFindingsGet]:
    """List Findings

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListFindingsApiV1ExtGrcFindingsGetResponseListFindingsApiV1ExtGrcFindingsGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> ListFindingsApiV1ExtGrcFindingsGetResponseListFindingsApiV1ExtGrcFindingsGet | None:
    """List Findings

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListFindingsApiV1ExtGrcFindingsGetResponseListFindingsApiV1ExtGrcFindingsGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
