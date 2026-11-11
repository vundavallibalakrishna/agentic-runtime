"""Dicts that remember which rows a request changed.

A change keeps a baseline until a flush commits it. A failed flush restores
that baseline and drops the change, so one bad write cannot stay dirty and
fail every later request on the process.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import SupportsIndex

_ABSENT = object()
_MISSING = object()


class TrackedList(list[object]):
    """A list whose mutations mark the parent row dirty."""

    def __init__(self, bucket: Any, key: object, items: list[object]) -> None:
        super().__init__(items)
        self._bucket = bucket
        self._key = key

    def _touch(self) -> None:
        self._bucket.touch(self._key)

    def append(self, item: object) -> None:
        self._bucket.capture(self._key)
        super().append(item)
        self._touch()

    def extend(self, items: object) -> None:
        self._bucket.capture(self._key)
        super().extend(items)  # type: ignore[arg-type]
        self._touch()

    def __setitem__(self, index: SupportsIndex | slice[Any, Any, Any], value: Any) -> None:
        self._bucket.capture(self._key)
        if isinstance(index, slice):
            items = list(value) if isinstance(value, Iterable) else []
            super().__setitem__(index, items)
        else:
            super().__setitem__(index, value)
        self._touch()

    def pop(self, index: SupportsIndex = -1) -> object:
        self._bucket.capture(self._key)
        found = super().pop(index)
        self._touch()
        return found


class TrackedRow(dict[str, object]):
    """A row dict. Field writes mark the bucket key dirty."""

    def __init__(self, bucket: Any, key: object, data: dict[object, object]) -> None:
        super().__init__()
        self._bucket = bucket
        self._key = key
        for name, value in data.items():
            super().__setitem__(str(name), _wrap(bucket, key, value))
        bucket.touch(key)

    def __setitem__(self, key: str, value: object) -> None:
        self._bucket.capture(self._key)
        super().__setitem__(key, _wrap(self._bucket, self._key, value))
        self._bucket.touch(self._key)


class TrackedDict(dict[object, object]):
    """``store.<bucket>`` replacement. Assignment records the key."""

    def __init__(self, store: Any, kind: str) -> None:
        super().__init__()
        self.store = store
        self.kind = kind
        self.dirty: set[object] = set()
        self.deleted: dict[object, object] = {}
        # key -> value before the uncommitted change, or ``_ABSENT`` when the key is new.
        self.baseline: dict[object, object] = {}

    def capture(self, key: object) -> None:
        """Remember the committed value the first time a unit changes ``key``."""
        if getattr(self.store, "reloading", False):
            return
        if key in self.baseline or key in self.dirty:
            return
        if key in self:
            self.baseline[key] = _detach(self[key])
        else:
            self.baseline[key] = _ABSENT

    def commit_keys(self, keys: Iterable[object]) -> None:
        """A flush committed these keys. The next change baselines from here."""
        for key in keys:
            self.baseline.pop(key, None)

    def rollback_keys(self, keys: Iterable[object]) -> None:
        """Drop an uncommitted change. A key touched again during the flush stays."""
        was = getattr(self.store, "reloading", False)
        for key in keys:
            if key in self.dirty:
                continue
            previous = self.baseline.pop(key, _MISSING)
            self.deleted.pop(key, None)
            self.store.reloading = True
            try:
                if previous is _ABSENT:
                    self.evict(key)
                elif previous is not _MISSING:
                    self[key] = previous
            finally:
                self.store.reloading = was
            self.dirty.discard(key)
            self.baseline.pop(key, None)

    def touch(self, key: object) -> None:
        if not getattr(self.store, "reloading", False):
            self.dirty.add(key)

    def __setitem__(self, key: object, value: object) -> None:
        self.deleted.pop(key, None)
        self.capture(key)
        if isinstance(value, list):
            stored: object = (
                value if isinstance(value, TrackedList) else TrackedList(self, key, value)
            )
            super().__setitem__(key, stored)
        elif isinstance(value, dict):
            stored = value if isinstance(value, TrackedRow) else TrackedRow(self, key, value)
            super().__setitem__(key, stored)
        else:
            super().__setitem__(key, value)
        self.touch(key)

    def __delitem__(self, key: object) -> None:
        self.capture(key)
        self.deleted[key] = self[key]
        super().__delitem__(key)
        self.touch(key)

    def pop(self, key: object, default: object = None) -> object:
        self.capture(key)
        if key in self:
            self.deleted[key] = self[key]
        found = super().pop(key, default)
        self.touch(key)
        return found

    def evict(self, key: object) -> None:
        """Drop a cache entry. The database row stays."""
        super().pop(key, None)
        self.dirty.discard(key)
        self.deleted.pop(key, None)


def _wrap(bucket: Any, key: object, value: object) -> object:
    if isinstance(value, dict) and not isinstance(value, TrackedRow):
        nested = TrackedRow(bucket, key, {})
        for name, item in value.items():
            nested[str(name)] = item
        return nested
    if isinstance(value, list) and not isinstance(value, TrackedList):
        return TrackedList(bucket, key, list(value))
    return value


BUCKETS = (
    "agents",
    "versions",
    "routines",
    "routine_events",
    "conversations",
    "messages",
    "runs",
    "events",
    "tool_calls",
    "policies",
    "policy_versions",
    "approvals",
    "approval_decisions",
    "sandboxes",
    "human_questions",
    "agent_api_keys",
    "agent_api_idempotency",
    "agent_api_grants",
    "a2a_tasks",
    "skills",
    "skill_versions",
    "memory_facts",
    "knowledge_collections",
    "knowledge_sources",
    "knowledge_documents",
    "document_chunks",
    "tool_servers",
    "tool_server_versions",
    "tool_defs",
    "tool_versions",
    "service_connections",
    "data_connections",
    "connector_installs",
    "credential_providers",
    "credential_grants",
    "oauth_states",
    "named_secrets",
    "library_documents",
    "document_checks",
    "document_comparisons",
    "document_rewrites",
    "rule_sets",
    "judgements",
    "channel_integrations",
    "channel_identities",
    "channel_threads",
    "channel_posts",
    "eval_suites",
    "eval_cases",
    "eval_runs",
    "eval_results",
    "files",
    "workspace_files",
    "job_progress",
    "a2a_push_configs",
    "tool_search_vectors",
    "standing_approvals",
    "review_queues",
    "review_items",
)


def install_tracking(store: Any) -> None:
    """Replace product dicts so later writes can be flushed."""
    for name in BUCKETS:
        current = getattr(store, name, None)
        if isinstance(current, TrackedDict):
            continue
        if not isinstance(current, dict):
            continue
        tracked = TrackedDict(store, name)
        store.reloading = True
        try:
            for key, value in current.items():
                tracked[key] = value
        finally:
            store.reloading = False
        tracked.dirty.clear()
        tracked.baseline.clear()
        setattr(store, name, tracked)


def snapshot_keys(rows: list[dict[str, Any]]) -> list[object]:
    """The bucket keys a flush snapshot copied."""
    return [row.get("id", row.get("_key")) for row in rows]


def commit_snapshot(store: Any, pending: dict[str, list[dict[str, Any]]]) -> None:
    """The transaction committed. Baselines for those keys are no longer needed."""
    for name, rows in pending.items():
        bucket = getattr(store, name, None)
        if isinstance(bucket, TrackedDict):
            bucket.commit_keys(snapshot_keys(rows))


def rollback_snapshot(store: Any, pending: dict[str, list[dict[str, Any]]]) -> None:
    """The transaction rolled back. Discard that unit so the next request is clean."""
    for name, rows in pending.items():
        bucket = getattr(store, name, None)
        if isinstance(bucket, TrackedDict):
            bucket.rollback_keys(snapshot_keys(rows))


def _detach(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _detach(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_detach(item) for item in value]
    return value
