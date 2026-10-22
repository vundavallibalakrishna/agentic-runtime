from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Unset
from typing import cast


def _get_kwargs(
    *,
    return_to: str | Unset = "/",
    tenant: None | str | Unset = UNSET,
    idp: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["return_to"] = return_to

    json_tenant: None | str | Unset
    if isinstance(tenant, Unset):
        json_tenant = UNSET
    else:
        json_tenant = tenant
    params["tenant"] = json_tenant

    json_idp: None | str | Unset
    if isinstance(idp, Unset):
        json_idp = UNSET
    else:
        json_idp = idp
    params["idp"] = json_idp

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/auth/login",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = response.json()
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
) -> Response[Any | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    return_to: str | Unset = "/",
    tenant: None | str | Unset = UNSET,
    idp: None | str | Unset = UNSET,
) -> Response[Any | HTTPValidationError]:
    """Login

     Start the OIDC authorization-code flow.

    Args:
        return_to (str | Unset):  Default: '/'.
        tenant (None | str | Unset):
        idp (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        return_to=return_to,
        tenant=tenant,
        idp=idp,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    return_to: str | Unset = "/",
    tenant: None | str | Unset = UNSET,
    idp: None | str | Unset = UNSET,
) -> Any | HTTPValidationError | None:
    """Login

     Start the OIDC authorization-code flow.

    Args:
        return_to (str | Unset):  Default: '/'.
        tenant (None | str | Unset):
        idp (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        return_to=return_to,
        tenant=tenant,
        idp=idp,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    return_to: str | Unset = "/",
    tenant: None | str | Unset = UNSET,
    idp: None | str | Unset = UNSET,
) -> Response[Any | HTTPValidationError]:
    """Login

     Start the OIDC authorization-code flow.

    Args:
        return_to (str | Unset):  Default: '/'.
        tenant (None | str | Unset):
        idp (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        return_to=return_to,
        tenant=tenant,
        idp=idp,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    return_to: str | Unset = "/",
    tenant: None | str | Unset = UNSET,
    idp: None | str | Unset = UNSET,
) -> Any | HTTPValidationError | None:
    """Login

     Start the OIDC authorization-code flow.

    Args:
        return_to (str | Unset):  Default: '/'.
        tenant (None | str | Unset):
        idp (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            return_to=return_to,
            tenant=tenant,
            idp=idp,
        )
    ).parsed
