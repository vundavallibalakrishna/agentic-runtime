from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.verify_api_v1_audit_events_verify_post_response_verify_api_v1_audit_events_verify_post import VerifyApiV1AuditEventsVerifyPostResponseVerifyApiV1AuditEventsVerifyPost
from typing import cast



def _get_kwargs(
    
) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/audit-events:verify",
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> VerifyApiV1AuditEventsVerifyPostResponseVerifyApiV1AuditEventsVerifyPost | None:
    if response.status_code == 200:
        response_200 = VerifyApiV1AuditEventsVerifyPostResponseVerifyApiV1AuditEventsVerifyPost.from_dict(response.json())



        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[VerifyApiV1AuditEventsVerifyPostResponseVerifyApiV1AuditEventsVerifyPost]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,

) -> Response[VerifyApiV1AuditEventsVerifyPostResponseVerifyApiV1AuditEventsVerifyPost]:
    """ Verify

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[VerifyApiV1AuditEventsVerifyPostResponseVerifyApiV1AuditEventsVerifyPost]
     """


    kwargs = _get_kwargs(
        
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    *,
    client: AuthenticatedClient | Client,

) -> VerifyApiV1AuditEventsVerifyPostResponseVerifyApiV1AuditEventsVerifyPost | None:
    """ Verify

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        VerifyApiV1AuditEventsVerifyPostResponseVerifyApiV1AuditEventsVerifyPost
     """


    return sync_detailed(
        client=client,

    ).parsed

async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,

) -> Response[VerifyApiV1AuditEventsVerifyPostResponseVerifyApiV1AuditEventsVerifyPost]:
    """ Verify

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[VerifyApiV1AuditEventsVerifyPostResponseVerifyApiV1AuditEventsVerifyPost]
     """


    kwargs = _get_kwargs(
        
    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    *,
    client: AuthenticatedClient | Client,

) -> VerifyApiV1AuditEventsVerifyPostResponseVerifyApiV1AuditEventsVerifyPost | None:
    """ Verify

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        VerifyApiV1AuditEventsVerifyPostResponseVerifyApiV1AuditEventsVerifyPost
     """


    return (await asyncio_detailed(
        client=client,

    )).parsed
