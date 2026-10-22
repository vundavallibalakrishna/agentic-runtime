"""Shared activity options."""

from datetime import timedelta

from temporalio.common import RetryPolicy

RETRY = RetryPolicy(
    maximum_attempts=5,
    initial_interval=timedelta(seconds=2),
    maximum_interval=timedelta(minutes=2),
    non_retryable_error_types=["unsupported_format", "too_large", "access_denied"],
)
TIMEOUT = timedelta(minutes=5)
