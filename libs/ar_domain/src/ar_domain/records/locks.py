"""A row is locked when an active hold names it.

The hold product lives in a pack. Core still has to see the lock so erasure and a
pack uninstall do not destroy a row the hold covers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.records.memory import bucket

if TYPE_CHECKING:
    from typing import Any


def is_held(store: Any, record_class: str, record_id: object) -> bool:
    for member in bucket(store, "hold_members").values():
        if member.get("record_class") == record_class and member.get("record_id") == record_id:
            hold = bucket(store, "holds").get(member.get("hold_id"))
            if isinstance(hold, dict) and hold.get("status") == "active":
                return True
    return False
