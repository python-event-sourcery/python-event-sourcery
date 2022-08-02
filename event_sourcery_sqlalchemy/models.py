from sqlalchemy import BigInteger, Column, DateTime, Integer, String
from sqlalchemy.orm import as_declarative

from event_sourcery_sqlalchemy.guid import GUID
from event_sourcery_sqlalchemy.jsonb import JSONB


@as_declarative()  # TODO: How to get external Base? Or how to extend existing one?
class Base:
    pass


class Stream(Base):
    __tablename__ = "event_sourcery_streams"

    uuid = Column(GUID(), primary_key=True)
    version = Column(BigInteger(), nullable=False)


class Event(Base):
    __tablename__ = "event_sourcery_events"

    id = Column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    uuid = Column(GUID(), index=True, unique=True)
    stream_id = Column(GUID(), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    data = Column(JSONB(), nullable=False)
    event_metadata = Column(JSONB(), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)


class Snapshot(Base):
    __tablename__ = "event_sourcery_snapshots"

    uuid = Column(GUID, primary_key=True)
    stream_id = Column(GUID(), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    data = Column(JSONB(), nullable=False)
    event_metadata = Column(JSONB(), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class OutboxEntry(Base):
    __tablename__ = "event_sourcery_outbox_entries"

    id = Column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    data = Column(JSONB(), nullable=False)
    tries_left = Column(Integer(), nullable=False, server_default="3")
