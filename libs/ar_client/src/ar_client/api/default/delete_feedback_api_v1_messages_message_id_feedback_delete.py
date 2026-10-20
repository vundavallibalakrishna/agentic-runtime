from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_feedback_api_v1_messages_message_id_feedback_delete_response_delete_feedback_api_v1_messages_message_id_feedback_delete import DeleteFeedbackApiV1MessagesMessageIdFeedbackDeleteResponseDeleteFeedbackApiV1MessagesMessageIdFeedbackDelete
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID



def _get_kwargs(
    message_id: UUID,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/messages/{message_id}/feedback".format(message_id=quote(str(message_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> DeleteFeedbackApiV1MessagesMessageIdFeedbackDeleteResponseDeleteFeedbackApiV1MessagesMessageIdFeedbackDelete | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = DeleteFeedbackApiV1MessagesMessageIdFeedbackDeleteResponseDeleteFeedbackApiV1MessagesMessageIdFeedbackDelete.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[DeleteFeedbackApiV1MessagesMessageIdFeedbackDeleteResponseDeleteFeedbackApiV1MessagesMessageIdFeedbackDelete | HTTPValidationError]:
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

) -> Response[DeleteFeedbackApiV1MessagesMessageIdFeedbackDeleteResponseDeleteFeedbackApiV1MessagesMessageIdFeedbackDelete | HTTPValidationError]:
    """ Delete Feedback

    Args:
        message_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteFeedbackApiV1MessagesMessageIdFeedbackDeleteResponseDeleteFeedbackApiV1MessagesMessageIdFeedbackDelete | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        message_id=message_id,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeleteFeedbackApiV1MessagesMessageIdFeedbackDeleteResponseDeleteFeedbackApiV1MessagesMessageIdFeedbackDelete | HTTPValidationError | None:
    """ Delete Feedback

    Args:
        message_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteFeedbackApiV1MessagesMessageIdFeedbackDeleteResponseDeleteFeedbackApiV1MessagesMessageIdFeedbackDelete | HTTPValidationError
     """


    return sync_detailed(
        message_id=message_id,
client=client,

    ).parsed

async def asyncio_detailed(
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[DeleteFeedbackApiV1MessagesMessageIdFeedbackDeleteResponseDeleteFeedbackApiV1MessagesMessageIdFeedbackDelete | HTTPValidationError]:
    """ Delete Feedback

    Args:
        message_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteFeedbackApiV1MessagesMessageIdFeedbackDeleteResponseDeleteFeedbackApiV1MessagesMessageIdFeedbackDelete | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        message_id=message_id,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    message_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeleteFeedbackApiV1MessagesMessageIdFeedbackDeleteResponseDeleteFeedbackApiV1MessagesMessageIdFeedbackDelete | HTTPValidationError | None:
    """ Delete Feedback

    Args:
        message_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteFeedbackApiV1MessagesMessageIdFeedbackDeleteResponseDeleteFeedbackApiV1MessagesMessageIdFeedbackDelete | HTTPValidationError
     """


    return (await asyncio_detailed(
        message_id=message_id,
client=client,

    )).parsed
