from collections.abc import Iterator
from contextlib import contextmanager
from typing import ClassVar

from event_sourcery.event_store import Event


class Aggregate:
    category: ClassVar[str]
    _changes: list[Event]

    @contextmanager
    def __persisting_changes__(self) -> Iterator[Iterator[Event]]:
        yield iter(getattr(self, "_changes", []))
        self._changes = []

    def __apply__(self, event: Event) -> None:
        raise NotImplementedError

    def _emit(self, event: Event) -> None:
        if not hasattr(self, "_changes"):
            self._changes = []
        self.__apply__(event)
        self._changes.append(event)
