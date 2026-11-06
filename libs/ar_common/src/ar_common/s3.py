"""S3-compatible object storage. Async I/O via aiobotocore; sync I/O and presign via boto3.

Spec: docs/02-architecture/adr/ADR-0014-object-storage.md.
"""

import asyncio
from typing import TYPE_CHECKING, Any, cast

import aiobotocore.session
import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

if TYPE_CHECKING:
    from ar_common.settings import BaseServiceSettings


class ObjectStoreError(Exception):
    """The object store did not do what was asked. The message names the endpoint."""


class S3Store:
    """Small wrapper around the configured object-storage bucket."""

    def __init__(self, settings: BaseServiceSettings) -> None:
        self._settings = settings
        self._session = aiobotocore.session.get_session()
        self._sync: Any = None

    @property
    def endpoint(self) -> str:
        return self._settings.s3_endpoint

    @property
    def bucket(self) -> str:
        return self._settings.s3_bucket

    # -- sync, for callers that wait through ``ar_common.offload.blocking`` ----------------

    def _client(self) -> Any:
        if self._sync is None:
            kwargs = self._client_kwargs(public=False)
            # An install with no key (the bundled SeaweedFS in dev) is talked to unsigned.
            signature = "s3v4" if self._settings.s3_access_key_id else UNSIGNED
            config = Config(signature_version=signature, retries={"max_attempts": 2})
            self._sync = boto3.client("s3", config=config, **kwargs)
        return self._sync

    def put(self, key: str, body: bytes, content_type: str) -> None:
        """Store an object. The configured bucket is made the first time it is missing."""
        params = {"Bucket": self.bucket, "Key": key, "Body": body, "ContentType": content_type}
        try:
            try:
                self._client().put_object(**params)
            except ClientError as exc:
                # A missing bucket answers NoSuchBucket on most stores and AccessDenied on
                # SeaweedFS; only a bucket that is really missing is made.
                code = exc.response.get("Error", {}).get("Code")
                if code not in {"NoSuchBucket", "AccessDenied"} or self._bucket_exists():
                    raise
                self._client().create_bucket(Bucket=self.bucket)
                self._client().put_object(**params)
        except (BotoCoreError, ClientError) as exc:
            raise ObjectStoreError(self._failed("store")) from exc

    def _bucket_exists(self) -> bool:
        try:
            self._client().head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchBucket", "NotFound"}:
                return False
            raise
        return True

    def get(self, key: str) -> bytes | None:
        """An object's bytes, or None when there is no such object."""
        try:
            found = self._client().get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "NoSuchBucket", "404"}:
                return None
            raise ObjectStoreError(self._failed("read")) from exc
        except BotoCoreError as exc:
            raise ObjectStoreError(self._failed("read")) from exc
        return cast("bytes", found["Body"].read())

    def delete(self, key: str) -> None:
        """Remove an object; one that is already gone is not an error."""
        try:
            self._client().delete_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "NoSuchBucket", "404"}:
                return
            raise ObjectStoreError(self._failed("remove")) from exc
        except BotoCoreError as exc:
            raise ObjectStoreError(self._failed("remove")) from exc

    def _failed(self, verb: str) -> str:
        return (
            f"The object store at {self.endpoint} (bucket {self.bucket}) did not {verb} the file. "
            "Check AR_S3_ENDPOINT, AR_S3_BUCKET, AR_S3_ACCESS_KEY_ID and AR_S3_SECRET_ACCESS_KEY."
        )

    # -- async --------------------------------------------------------------------------

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
