from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.alias_test_body import AliasTestBody
from ...models.http_validation_error import HTTPValidationError
from ...models.test_alias_api_v1_model_aliases_alias_id_test_post_response_test_alias_api_v1_model_aliases_alias_id_test_post import (
    TestAliasApiV1ModelAliasesAliasIdTestPostResponseTestAliasApiV1ModelAliasesAliasIdTestPost,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    alias_id: UUID,
    *,
    body: AliasTestBody,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/model-aliases/{alias_id}:test".format(
            alias_id=quote(str(alias_id), safe=""),
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
    | TestAliasApiV1ModelAliasesAliasIdTestPostResponseTestAliasApiV1ModelAliasesAliasIdTestPost
    | None
):
    if response.status_code == 200:
        response_200 = TestAliasApiV1ModelAliasesAliasIdTestPostResponseTestAliasApiV1ModelAliasesAliasIdTestPost.from_dict(
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
    | TestAliasApiV1ModelAliasesAliasIdTestPostResponseTestAliasApiV1ModelAliasesAliasIdTestPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    alias_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AliasTestBody,
) -> Response[
    HTTPValidationError
    | TestAliasApiV1ModelAliasesAliasIdTestPostResponseTestAliasApiV1ModelAliasesAliasIdTestPost
]:
    """Test Alias

    Args:
        alias_id (UUID):
        body (AliasTestBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | TestAliasApiV1ModelAliasesAliasIdTestPostResponseTestAliasApiV1ModelAliasesAliasIdTestPost]
    """

    kwargs = _get_kwargs(
        alias_id=alias_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    alias_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AliasTestBody,
) -> (
    HTTPValidationError
    | TestAliasApiV1ModelAliasesAliasIdTestPostResponseTestAliasApiV1ModelAliasesAliasIdTestPost
    | None
):
    """Test Alias

    Args:
        alias_id (UUID):
        body (AliasTestBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | TestAliasApiV1ModelAliasesAliasIdTestPostResponseTestAliasApiV1ModelAliasesAliasIdTestPost
    """

    return sync_detailed(
        alias_id=alias_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    alias_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AliasTestBody,
) -> Response[
    HTTPValidationError
    | TestAliasApiV1ModelAliasesAliasIdTestPostResponseTestAliasApiV1ModelAliasesAliasIdTestPost
]:
    """Test Alias

    Args:
        alias_id (UUID):
        body (AliasTestBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | TestAliasApiV1ModelAliasesAliasIdTestPostResponseTestAliasApiV1ModelAliasesAliasIdTestPost]
    """

    kwargs = _get_kwargs(
        alias_id=alias_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    alias_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: AliasTestBody,
) -> (
    HTTPValidationError
    | TestAliasApiV1ModelAliasesAliasIdTestPostResponseTestAliasApiV1ModelAliasesAliasIdTestPost
    | None
):
    """Test Alias

    Args:
        alias_id (UUID):
        body (AliasTestBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | TestAliasApiV1ModelAliasesAliasIdTestPostResponseTestAliasApiV1ModelAliasesAliasIdTestPost
    """

    return (
        await asyncio_detailed(
            alias_id=alias_id,
            client=client,
            body=body,
        )
    ).parsed
