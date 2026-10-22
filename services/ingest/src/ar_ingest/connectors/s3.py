"""S3 listings. Credentials stay in the secret store; tests pass object rows."""

from ar_ingest.connectors.base import ConfigSource


class S3Source(ConfigSource):
    kind = "s3"
