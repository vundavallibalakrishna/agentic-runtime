"""SQLAlchemy base. Spec: docs/04-data/schema.md."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Metadata shared by every domain model."""


metadata = Base.metadata
