from typing import Type

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import mapped_column, registry

from event_sourcery_sqlalchemy.guid import GUID
from event_sourcery_sqlalchemy.jsonb import JSONB


def configure_models(base: Type) -> None:
    for model_cls in (Stream, Event, Snapshot, OutboxEntry, ProjectorCursor):
        registry(metadata=base.metadata, class_registry={}).map_declaratively(model_cls)


class Stream:
    __tablename__ = "event_sourcery_streams"

    uuid = mapped_column(GUID(), primary_key=True)
    name = mapped_column(String(255), unique=True, nullable=True)
    version = mapped_column(BigInteger(), nullable=True)


class Event:
    __tablename__ = "event_sourcery_events"
    __table_args__ = (
        Index(
            "ix_events_stream_id_version",
            "stream_id",
            "version",
            unique=True,
        ),
    )

    id = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    version = mapped_column(Integer(), nullable=True)
    uuid = mapped_column(GUID(), index=True, unique=True)
    stream_id = mapped_column(GUID(), nullable=False, index=True)
    name = mapped_column(String(200), nullable=False)
    data = mapped_column(JSONB(), nullable=False)
    event_context = mapped_column(JSONB(), nullable=False)
    created_at = mapped_column(DateTime(), nullable=False, index=True)


class Snapshot:
    __tablename__ = "event_sourcery_snapshots"

    uuid = mapped_column(GUID, primary_key=True)
    version = mapped_column(Integer(), nullable=False)
    stream_id = mapped_column(GUID(), nullable=False, index=True)
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
            unique=True,
        ),
    )

    id = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    name = mapped_column(String(255), nullable=False)
    stream_id = mapped_column(GUID(), nullable=False, index=True)
    version = mapped_column(BigInteger(), nullable=False)
