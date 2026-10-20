from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_file_api_v1_files_file_id_get_response_get_file_api_v1_files_file_id_get import GetFileApiV1FilesFileIdGetResponseGetFileApiV1FilesFileIdGet
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID



def _get_kwargs(
    file_id: UUID,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/files/{file_id}".format(file_id=quote(str(file_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> GetFileApiV1FilesFileIdGetResponseGetFileApiV1FilesFileIdGet | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = GetFileApiV1FilesFileIdGetResponseGetFileApiV1FilesFileIdGet.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[GetFileApiV1FilesFileIdGetResponseGetFileApiV1FilesFileIdGet | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    file_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[GetFileApiV1FilesFileIdGetResponseGetFileApiV1FilesFileIdGet | HTTPValidationError]:
    """ Get File

    Args:
        file_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetFileApiV1FilesFileIdGetResponseGetFileApiV1FilesFileIdGet | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        file_id=file_id,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    file_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> GetFileApiV1FilesFileIdGetResponseGetFileApiV1FilesFileIdGet | HTTPValidationError | None:
    """ Get File

    Args:
        file_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetFileApiV1FilesFileIdGetResponseGetFileApiV1FilesFileIdGet | HTTPValidationError
     """


    return sync_detailed(
        file_id=file_id,
client=client,

    ).parsed

async def asyncio_detailed(
    file_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[GetFileApiV1FilesFileIdGetResponseGetFileApiV1FilesFileIdGet | HTTPValidationError]:
    """ Get File

    Args:
        file_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetFileApiV1FilesFileIdGetResponseGetFileApiV1FilesFileIdGet | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        file_id=file_id,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    file_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> GetFileApiV1FilesFileIdGetResponseGetFileApiV1FilesFileIdGet | HTTPValidationError | None:
    """ Get File

    Args:
        file_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetFileApiV1FilesFileIdGetResponseGetFileApiV1FilesFileIdGet | HTTPValidationError
     """


    return (await asyncio_detailed(
        file_id=file_id,
client=client,

    )).parsed
