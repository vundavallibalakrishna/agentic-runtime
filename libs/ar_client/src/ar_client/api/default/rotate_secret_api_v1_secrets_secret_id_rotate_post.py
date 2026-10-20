from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.rotate_secret_api_v1_secrets_secret_id_rotate_post_response_rotate_secret_api_v1_secrets_secret_id_rotate_post import RotateSecretApiV1SecretsSecretIdRotatePostResponseRotateSecretApiV1SecretsSecretIdRotatePost
from ...models.secret_rotate import SecretRotate
from typing import cast
from uuid import UUID



def _get_kwargs(
    secret_id: UUID,
    *,
    body: SecretRotate,

) -> dict[str, Any]:
    headers: dict[str, Any] = {}


    

    

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/secrets/{secret_id}:rotate".format(secret_id=quote(str(secret_id), safe=""),),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | RotateSecretApiV1SecretsSecretIdRotatePostResponseRotateSecretApiV1SecretsSecretIdRotatePost | None:
    if response.status_code == 200:
        response_200 = RotateSecretApiV1SecretsSecretIdRotatePostResponseRotateSecretApiV1SecretsSecretIdRotatePost.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | RotateSecretApiV1SecretsSecretIdRotatePostResponseRotateSecretApiV1SecretsSecretIdRotatePost]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    secret_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SecretRotate,

) -> Response[HTTPValidationError | RotateSecretApiV1SecretsSecretIdRotatePostResponseRotateSecretApiV1SecretsSecretIdRotatePost]:
    """ Rotate Secret

    Args:
        secret_id (UUID):
        body (SecretRotate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RotateSecretApiV1SecretsSecretIdRotatePostResponseRotateSecretApiV1SecretsSecretIdRotatePost]
     """


    kwargs = _get_kwargs(
        secret_id=secret_id,
body=body,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    secret_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SecretRotate,

) -> HTTPValidationError | RotateSecretApiV1SecretsSecretIdRotatePostResponseRotateSecretApiV1SecretsSecretIdRotatePost | None:
    """ Rotate Secret

    Args:
        secret_id (UUID):
        body (SecretRotate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RotateSecretApiV1SecretsSecretIdRotatePostResponseRotateSecretApiV1SecretsSecretIdRotatePost
     """


    return sync_detailed(
        secret_id=secret_id,
client=client,
body=body,

    ).parsed

async def asyncio_detailed(
    secret_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SecretRotate,

) -> Response[HTTPValidationError | RotateSecretApiV1SecretsSecretIdRotatePostResponseRotateSecretApiV1SecretsSecretIdRotatePost]:
    """ Rotate Secret

    Args:
        secret_id (UUID):
        body (SecretRotate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RotateSecretApiV1SecretsSecretIdRotatePostResponseRotateSecretApiV1SecretsSecretIdRotatePost]
     """


    kwargs = _get_kwargs(
        secret_id=secret_id,
body=body,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    secret_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SecretRotate,

) -> HTTPValidationError | RotateSecretApiV1SecretsSecretIdRotatePostResponseRotateSecretApiV1SecretsSecretIdRotatePost | None:
    """ Rotate Secret

    Args:
        secret_id (UUID):
        body (SecretRotate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RotateSecretApiV1SecretsSecretIdRotatePostResponseRotateSecretApiV1SecretsSecretIdRotatePost
     """


    return (await asyncio_detailed(
        secret_id=secret_id,
client=client,
body=body,

    )).parsed
