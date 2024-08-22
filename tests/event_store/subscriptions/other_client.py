import enum
from collections.abc import Callable
from contextlib import AbstractContextManager
from queue import Queue
from threading import Event as ThreadingEvent
from threading import Thread
from typing import Literal
from weakref import WeakSet

from typing_extensions import Protocol

from event_sourcery.event_store import BackendFactory, Metadata, StreamId


class Command(enum.Enum):
    STOP = enum.auto()
    APPEND = enum.auto()


class _Handle:
    TIMEOUT = 3

    def __init__(self) -> None:
        self._commit_event = ThreadingEvent()
        self._got_until_commit = ThreadingEvent()

    def wait_to_commit(self) -> None:
        self._got_until_commit.set()
        self._commit_event.wait(timeout=self.TIMEOUT)

    def process_up_to_commit(self) -> None:
        self._got_until_commit.wait(timeout=self.TIMEOUT)

    def commit(self) -> None:
        self._commit_event.set()


Message = (
    Literal[Command.STOP] | tuple[Literal[Command.APPEND], Metadata, StreamId, _Handle]
)


class Handle(Protocol):
    def commit(self) -> None: ...

    def process_up_to_commit(self) -> None: ...


class Inbox:
    def __init__(self) -> None:
        self._in_queue: Queue[Message] = Queue()
        self._pending_handles: WeakSet[_Handle] = WeakSet()

    def get(self) -> Message:
        return self._in_queue.get()

    def put_stop(self) -> None:
        for handle in self._pending_handles:
            handle.commit()
        self._in_queue.put(Command.STOP)

    def put_event_to_append(self, event: Metadata, stream_id: StreamId) -> Handle:
        handle = _Handle()
        self._in_queue.put((Command.APPEND, event, stream_id, handle))
        self._pending_handles.add(handle)
        return handle


class Agent(Thread):
    def __init__(
        self,
        event_store_factory: BackendFactory,
        transaction: Callable[[], AbstractContextManager],
        inbox: Inbox,
    ) -> None:
        super().__init__(daemon=True)
        self._event_store_factory = event_store_factory
        self._transaction = transaction
        self._inbox = inbox
        self.exception: Exception | None = None

    def run(self) -> None:
        try:
            backend = self._event_store_factory.build()
            event_store = backend.event_store

            while True:
                match self._inbox.get():
                    case (Command.APPEND, event, stream_id, _Handle() as sync):
                        with self._transaction():
                            event_store.append(event, stream_id=stream_id)
                            sync.wait_to_commit()
                    case Command.STOP:
                        break
                    case _:
                        pass
        except Exception as err:
            self.exception = err


class OtherClient:
    def __init__(
        self,
        event_store_factory: BackendFactory,
        transaction: Callable[[], AbstractContextManager],
    ) -> None:
        self._inbox = Inbox()
        self._thread = Agent(
            event_store_factory,
            transaction,
            self._inbox,
        )
        self._thread.start()

    def appends_in_transaction(self, event: Metadata, stream_id: StreamId) -> Handle:
        return self._inbox.put_event_to_append(event, stream_id)

    def stop(self) -> None:
        self._inbox.put_stop()
        self._raise_thread_exception()

    def _raise_thread_exception(self) -> None:
        exception = self._thread.exception
        if exception is not None:
            raise exception
