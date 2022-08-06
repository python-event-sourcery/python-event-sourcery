from typing import Type

from sqlalchemy import BigInteger, Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import instrument_declarative

from event_sourcery_sqlalchemy.guid import GUID
from event_sourcery_sqlalchemy.jsonb import JSONB


def configure_models(base: Type) -> None:
    for model_cls in (Stream, Event, Snapshot, OutboxEntry):
        instrument_declarative(model_cls, {}, base.metadata)


class Stream:
    __tablename__ = "event_sourcery_streams"

    uuid = Column(GUID(), primary_key=True)
    version = Column(BigInteger(), nullable=False)


class Event:
    __tablename__ = "event_sourcery_events"

    id = Column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    uuid = Column(GUID(), index=True, unique=True)
    stream_id = Column(GUID(), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    data = Column(JSONB(), nullable=False)
    event_metadata = Column(JSONB(), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)


class Snapshot:
    __tablename__ = "event_sourcery_snapshots"

    uuid = Column(GUID, primary_key=True)
    stream_id = Column(GUID(), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    data = Column(JSONB(), nullable=False)
    event_metadata = Column(JSONB(), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class OutboxEntry:
    __tablename__ = "event_sourcery_outbox_entries"

    id = Column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    data = Column(JSONB(), nullable=False)
    tries_left = Column(Integer(), nullable=False, server_default="3")
