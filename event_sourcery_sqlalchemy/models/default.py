from event_sourcery_sqlalchemy.models.base import (
    BaseEvent,
    BaseOutboxEntry,
    BaseProjectorCursor,
    BaseSnapshot,
    BaseStream,
)


class DefaultStream(BaseStream):
    __tablename__ = "event_sourcery_streams"


class DefaultEvent(BaseEvent):
    __tablename__ = "event_sourcery_events"


class DefaultSnapshot(BaseSnapshot):
    __tablename__ = "event_sourcery_snapshots"


class DefaultOutboxEntry(BaseOutboxEntry):
    __tablename__ = "event_sourcery_outbox_entries"


class DefaultProjectorCursor(BaseProjectorCursor):
    __tablename__ = "event_sourcery_projector_cursors"
