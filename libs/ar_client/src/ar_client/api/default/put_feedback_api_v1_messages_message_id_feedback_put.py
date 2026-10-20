from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.feedback_body import FeedbackBody
from ...models.http_validation_error import HTTPValidationError
from ...models.put_feedback_api_v1_messages_message_id_feedback_put_response_put_feedback_api_v1_messages_message_id_feedback_put import PutFeedbackApiV1MessagesMessageIdFeedbackPutResponsePutFeedbackApiV1MessagesMessageIdFeedbackPut
from typing import cast
from uuid import UUID



def _get_kwargs(
    message_id: UUID,
    *,
    body: FeedbackBody,

) -> dict[str, Any]:
    headers: dict[str, Any] = {}


    

    

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/api/v1/messages/{message_id}/feedback".format(message_id=quote(str(message_id), safe=""),),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | PutFeedbackApiV1MessagesMessageIdFeedbackPutResponsePutFeedbackApiV1MessagesMessageIdFeedbackPut | None:
    if response.status_code == 200:
        response_200 = PutFeedbackApiV1MessagesMessageIdFeedbackPutResponsePutFeedbackApiV1MessagesMessageIdFeedbackPut.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | PutFeedbackApiV1MessagesMessageIdFeedbackPutResponsePutFeedbackApiV1MessagesMessageIdFeedbackPut]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: FeedbackBody,

) -> Response[HTTPValidationError | PutFeedbackApiV1MessagesMessageIdFeedbackPutResponsePutFeedbackApiV1MessagesMessageIdFeedbackPut]:
    """ Put Feedback

    Args:
        message_id (UUID):
        body (FeedbackBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PutFeedbackApiV1MessagesMessageIdFeedbackPutResponsePutFeedbackApiV1MessagesMessageIdFeedbackPut]
     """


    kwargs = _get_kwargs(
        message_id=message_id,
body=body,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: FeedbackBody,

) -> HTTPValidationError | PutFeedbackApiV1MessagesMessageIdFeedbackPutResponsePutFeedbackApiV1MessagesMessageIdFeedbackPut | None:
    """ Put Feedback

    Args:
        message_id (UUID):
        body (FeedbackBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PutFeedbackApiV1MessagesMessageIdFeedbackPutResponsePutFeedbackApiV1MessagesMessageIdFeedbackPut
     """


    return sync_detailed(
        message_id=message_id,
client=client,
body=body,

    ).parsed

async def asyncio_detailed(
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: FeedbackBody,

) -> Response[HTTPValidationError | PutFeedbackApiV1MessagesMessageIdFeedbackPutResponsePutFeedbackApiV1MessagesMessageIdFeedbackPut]:
    """ Put Feedback

    Args:
        message_id (UUID):
        body (FeedbackBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PutFeedbackApiV1MessagesMessageIdFeedbackPutResponsePutFeedbackApiV1MessagesMessageIdFeedbackPut]
     """


    kwargs = _get_kwargs(
        message_id=message_id,
body=body,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: FeedbackBody,

) -> HTTPValidationError | PutFeedbackApiV1MessagesMessageIdFeedbackPutResponsePutFeedbackApiV1MessagesMessageIdFeedbackPut | None:
    """ Put Feedback

    Args:
        message_id (UUID):
        body (FeedbackBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PutFeedbackApiV1MessagesMessageIdFeedbackPutResponsePutFeedbackApiV1MessagesMessageIdFeedbackPut
     """


    return (await asyncio_detailed(
        message_id=message_id,
client=client,
body=body,

    )).parsed
