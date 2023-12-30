from typing import Iterator

from event_sourcery.event_store import Entry


class InTransactionSubscription(Iterator[Entry]):
    def __next__(self) -> Entry:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
