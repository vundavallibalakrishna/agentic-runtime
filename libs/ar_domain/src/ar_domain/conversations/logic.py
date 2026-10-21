"""Branch activation and run guards. Spec: docs/03-specs/06-conversations-runs.md."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MessageNode:
    """One message in a conversation branch."""

    id: str
    parent_id: str | None
    is_active: bool


def active_chain(messages: list[MessageNode]) -> list[str]:
    """Ids on the active branch, oldest first."""
    by_parent: dict[str | None, MessageNode] = {}
    for message in messages:
        if message.is_active:
            by_parent[message.parent_id] = message
    chain: list[str] = []
    parent: str | None = None
    seen: set[str] = set()
    while parent in by_parent and by_parent[parent].id not in seen:
        node = by_parent[parent]
        seen.add(node.id)
        chain.append(node.id)
        parent = node.id
    return chain


def activate_branch(messages: list[MessageNode], message_id: str) -> dict[str, bool]:
    """Mark the path to ``message_id`` active and its siblings inactive."""
    by_id = {message.id: message for message in messages}
    if message_id not in by_id:
        return {}
    wanted: set[str] = set()
    cursor: str | None = message_id
    while cursor is not None and cursor in by_id:
        wanted.add(cursor)
        cursor = by_id[cursor].parent_id
    # Keep descendants of the chosen message that were already the only child path.
    children: dict[str | None, list[MessageNode]] = {}
    for message in messages:
        children.setdefault(message.parent_id, []).append(message)
    frontier = [message_id]
    while frontier:
        current = frontier.pop()
        kids = children.get(current, [])
        if len(kids) == 1:
            wanted.add(kids[0].id)
            frontier.append(kids[0].id)
    return {message.id: message.id in wanted for message in messages}


def run_is_active(status: str) -> bool:
    return status in {"queued", "running", "waiting_approval", "waiting_input"}
