import sys
from datetime import date, datetime
from typing import Iterator
from uuid import UUID

from pydantic import Field

from event_sourcery.event_store import Event, Metadata

sequence: Iterator[int]
actual_version = 0


def init_version() -> None:
    global sequence
    global actual_version
    sequence = iter(range(1, sys.maxsize))
    actual_version = 0


def next_version() -> int:
    global actual_version
    global sequence
    actual_version = next(sequence)
    return actual_version


class AnEvent(Metadata):
    class _Event(Event):
        pass

    event: _Event = Field(default_factory=_Event)
    version: int = Field(default_factory=next_version)


class Snapshot(Metadata):
    class _Event(Event):
        pass

    event: _Event = Field(default_factory=_Event)
    version: int = Field(default_factory=lambda: actual_version)


class NastyEventWithJsonUnfriendlyTypes(Event):
    uuid: UUID
    a_datetime: datetime
    second_datetime: datetime
    a_date: date
