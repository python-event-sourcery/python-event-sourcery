from contextlib import contextmanager
from typing import Iterator

from event_sourcery.interfaces.event import TEvent


class Aggregate:
    def __init__(self) -> None:
        self.__changes: list[TEvent] = []

    @contextmanager
    def __persisting_changes__(self) -> Iterator[Iterator[TEvent]]:
        yield iter(self.__changes)
        self.__changes = []

    def __apply__(self, event: TEvent) -> None:
        raise NotImplementedError

    def _emit(self, event: TEvent) -> None:
        self.__apply__(event)
        self.__changes.append(event)
