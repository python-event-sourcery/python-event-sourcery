from __future__ import annotations

from typing import Any, Type, cast

from sqlalchemy import (
    BigInteger,
    Column,
    ColumnElement,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    and_,
)
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.ext.hybrid import Comparator, hybrid_property
from sqlalchemy.orm import Composite, Mapped, mapped_column, registry, relationship

from event_sourcery import StreamId
from event_sourcery_sqlalchemy.guid import GUID
from event_sourcery_sqlalchemy.jsonb import JSONB


def configure_models(base: Type) -> None:
    for model_cls in (Stream, Event, Snapshot, OutboxEntry, ProjectorCursor):
        registry(metadata=base.metadata, class_registry={}).map_declaratively(model_cls)


class StreamIdComparator(Comparator[StreamId]):
    def __init__(self, uuid: Column, name: Column, category: Column) -> None:
        super().__init__(Composite(uuid, name, category))

    def __eq__(self, other: Any) -> ColumnElement[bool]:
        uuid, name, category = cast(Composite, self.__clause_element__()).attrs
        same_stream_id = cast(
            ColumnElement[Type[bool]],
            name == other.name if other.name else uuid == other,
        )
        same_category = cast(ColumnElement[bool], category == (other.category or ""))
        return and_(same_stream_id, same_category)


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
    stream_id: Mapped[StreamId]

    @hybrid_property
    def stream_id(self) -> StreamId:
        return StreamId(self.uuid, self.name, category=self.category or None)

    @stream_id.setter
    def stream_id(self, value: StreamId) -> None:
        self.uuid = value
        self.name = value.name
        self.category = value.category or ""

    @stream_id.comparator
    @classmethod
    def stream_id(cls) -> StreamIdComparator:
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
    stream = relationship(Stream, backref="events")
    stream_id: AssociationProxy[StreamId] = association_proxy("stream", "stream_id")
    name = mapped_column(String(200), nullable=False)
    data = mapped_column(JSONB(), nullable=False)
    event_context = mapped_column(JSONB(), nullable=False)
    created_at = mapped_column(DateTime(), nullable=False, index=True)


class Snapshot:
    __tablename__ = "event_sourcery_snapshots"

    uuid = mapped_column(GUID, primary_key=True)
    version = mapped_column(Integer(), nullable=False)
    _db_stream_id = mapped_column(
        "db_stream_id",
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey(Stream.id),
        nullable=False,
        index=True,
    )
    stream = relationship(Stream, backref="snapshots")
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
    tries_left = mapped_column(Integer(), nullable=False, server_default="3")


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
