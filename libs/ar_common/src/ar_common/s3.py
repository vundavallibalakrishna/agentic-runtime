"""S3-compatible object storage. Async I/O via aiobotocore; presign via boto3.

Spec: docs/02-architecture/adr/ADR-0014-object-storage.md.
"""

import asyncio
from typing import TYPE_CHECKING, cast

import aiobotocore.session
import boto3
from botocore.config import Config

if TYPE_CHECKING:
    from ar_common.settings import BaseServiceSettings


class S3Store:
    """Small wrapper around the configured object-storage bucket."""

    def __init__(self, settings: BaseServiceSettings) -> None:
        self._settings = settings
        self._session = aiobotocore.session.get_session()

    def _client_kwargs(self, *, public: bool) -> dict[str, object]:
        endpoint = self._settings.s3_public_endpoint if public else self._settings.s3_endpoint
        return {
            "endpoint_url": endpoint,
            "region_name": self._settings.s3_region,
            "aws_access_key_id": self._settings.s3_access_key_id or None,
            "aws_secret_access_key": self._settings.s3_secret_access_key.get_secret_value() or None,
        }

    async def put_bytes(self, key: str, body: bytes, content_type: str) -> None:
        """Store an object."""
        kwargs = self._client_kwargs(public=False)
        async with self._session.create_client("s3", **kwargs) as client:
            await client.put_object(
                Bucket=self._settings.s3_bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
            )

    async def presign_get(self, key: str) -> str:
        """Return a presigned GET URL using the browser-reachable endpoint."""
        settings = self._settings

        def sign() -> str:
            client = boto3.client(
                "s3",
                endpoint_url=settings.s3_public_endpoint,
                region_name=settings.s3_region,
                aws_access_key_id=settings.s3_access_key_id or None,
                aws_secret_access_key=settings.s3_secret_access_key.get_secret_value() or None,
                config=Config(signature_version="s3v4"),
            )
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.s3_bucket, "Key": key},
                ExpiresIn=settings.s3_presign_ttl_s,
            )
            return cast("str", url)

        return await asyncio.to_thread(sign)
