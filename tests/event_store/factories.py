import sys
from typing import Iterator

from pydantic import Field

from event_sourcery import Event, Metadata

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
