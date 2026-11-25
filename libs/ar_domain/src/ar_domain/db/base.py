"""Declarative base and constraint naming. Spec: docs/04-data/schema.md §0."""

from sqlalchemy import MetaData, event
from sqlalchemy.orm import DeclarativeBase

from ar_common.ids import new_id
from ar_domain.db.types import ID_AT_BIRTH

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Metadata shared by every domain model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


metadata = Base.metadata


@event.listens_for(Base, "init", propagate=True)
def _id_at_birth(target: object, args: object, kwargs: dict[str, object]) -> None:
    """Give a new row its id as it is made.

    A column default is applied when the row is saved. Code that makes a row and then
    names it, in a reply, an audit entry or an event, did so before the save and wrote
    "None": creating a service account answered with no id, so nothing could be done
    with it. The id is the same one the save would have made.
    """
    del args
    table = getattr(type(target), "__table__", None)
    column = None if table is None else table.columns.get("id")
    if column is not None and column.info.get(ID_AT_BIRTH) and kwargs.get("id") is None:
        kwargs["id"] = new_id()
