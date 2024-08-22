from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    ColumnElement,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    and_,
    true,
)
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.ext.hybrid import Comparator, hybrid_property
from sqlalchemy.orm import (
    Composite,
    InstrumentedAttribute,
    Mapped,
    mapped_column,
    registry,
    relationship,
)

from event_sourcery.event_store import StreamId
from event_sourcery_sqlalchemy.guid import GUID
from event_sourcery_sqlalchemy.jsonb import JSONB


def configure_models(base: type[Any]) -> None:
    for model_cls in (Stream, Event, Snapshot, OutboxEntry, ProjectorCursor):
        registry(metadata=base.metadata, class_registry={}).map_declaratively(model_cls)


class StreamIdComparator(Comparator[StreamId]):
    def __init__(
        self,
        uuid: InstrumentedAttribute,
        name: InstrumentedAttribute,
        category: InstrumentedAttribute,
    ) -> None:
        super().__init__(Composite(uuid, name, category))

    def __eq__(self, other: Any) -> ColumnElement[bool]:  # type: ignore[override]
        uuid, name, category = cast(Composite, self.__clause_element__()).attrs
        same_uuid = cast(ColumnElement[bool], uuid == other)
        same_name = cast(
            ColumnElement[bool], name == other.name if other.name else true()
        )
        same_category = cast(ColumnElement[bool], category == (other.category or ""))
        return and_(same_uuid, same_name, same_category)


class Stream:
    __tablename__ = "event_sourcery_streams"
    __table_args__ = (
        UniqueConstraint("uuid", "category"),
        UniqueConstraint("name", "category"),
    )

    id = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    uuid = mapped_column(GUID(), nullable=False)
    name = mapped_column(String(255), nullable=True, default=None)
    category = mapped_column(String(255), nullable=False, default="")
    version = mapped_column(BigInteger(), nullable=True)

    events: Mapped[list["Event"]]
    snapshots: Mapped[list["Snapshot"]]

    @hybrid_property
    def stream_id(self) -> StreamId:
        return StreamId(self.uuid, self.name, category=self.category or None)

    @stream_id.inplace.comparator
    @classmethod
    def _stream_id_comparator(cls) -> StreamIdComparator:
        return StreamIdComparator(cls.uuid, cls.name, cls.category)


class Event:
    __tablename__ = "event_sourcery_events"
    __table_args__ = (
        Index(
            "ix_events_stream_id_version",
            "db_stream_id",
            "version",
            unique=True,
        ),
    )

    def __init__(
        self,
        uuid: UUID,
        created_at: datetime,
        name: str,
        data: dict,
        event_context: dict,
        version: int | None,
    ) -> None:
        self.uuid = uuid
        self.created_at = created_at
        self.name = name
        self.data = data
        self.event_context = event_context
        self.version = version

    id = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    version = mapped_column(Integer(), nullable=True)
    uuid = mapped_column(GUID(), index=True, unique=True)
    _db_stream_id = mapped_column(
        "db_stream_id",
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey(Stream.id),
        nullable=False,
        index=True,
    )
    stream: Mapped[Stream] = relationship(Stream, back_populates="events")
    stream_id: AssociationProxy[StreamId] = association_proxy("stream", "stream_id")
    name = mapped_column(String(200), nullable=False)
    data = mapped_column(JSONB(), nullable=False)
    event_context = mapped_column(JSONB(), nullable=False)
    created_at = mapped_column(DateTime(), nullable=False, index=True)


class Snapshot:
    __tablename__ = "event_sourcery_snapshots"

    def __init__(
        self,
        uuid: UUID,
        created_at: datetime,
        name: str,
        data: dict,
        event_context: dict,
        version: int | None,
    ) -> None:
        self.uuid = uuid
        self.created_at = created_at
        self.name = name
        self.data = data
        self.event_context = event_context
        self.version = version

    uuid = mapped_column(GUID, primary_key=True)
    version = mapped_column(Integer(), nullable=False)
    _db_stream_id = mapped_column(
        "db_stream_id",
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey(Stream.id),
        nullable=False,
        index=True,
    )
    stream = relationship(Stream, back_populates="snapshots")
    stream_id: AssociationProxy[StreamId] = association_proxy("stream", "stream_id")
    name = mapped_column(String(50), nullable=False)
    data = mapped_column(JSONB(), nullable=False)
    event_context = mapped_column(JSONB(), nullable=False)
    created_at = mapped_column(DateTime(), nullable=False)


class OutboxEntry:
    __tablename__ = "event_sourcery_outbox_entries"

    id = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    created_at = mapped_column(DateTime(), nullable=False, index=True)
    data = mapped_column(JSONB(), nullable=False)
    stream_name = mapped_column(String(255), nullable=True)
    position = mapped_column(BigInteger().with_variant(Integer(), "sqlite"))
    tries_left = mapped_column(Integer(), nullable=False)


class ProjectorCursor:
    __tablename__ = "event_sourcery_projector_cursors"
    __table_args__ = (
        Index(
            "ix_name_stream_id",
            "name",
            "stream_id",
            "category",
            unique=True,
        ),
    )

    id = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    name = mapped_column(String(255), nullable=False)
    stream_id = mapped_column(GUID(), nullable=False, index=True)
    category = mapped_column(String(255), nullable=True)
    version = mapped_column(BigInteger(), nullable=False)


Stream.events = relationship(Event, back_populates="stream")
Stream.snapshots = relationship(Snapshot, back_populates="stream")
