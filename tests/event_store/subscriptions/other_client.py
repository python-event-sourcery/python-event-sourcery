import enum
from queue import Queue
from threading import Event as ThreadingEvent
from threading import Thread
from typing import Callable, ContextManager, Literal
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
    def commit(self) -> None:
        ...

    def process_up_to_commit(self) -> None:
        ...


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


def agent(
    event_store_factory: BackendFactory,
    transaction: Callable[[], ContextManager],
    inbox: Inbox,
) -> None:
    backend = event_store_factory.build()
    event_store = backend.event_store

    while True:
        match inbox.get():
            case (Command.APPEND, event, stream_id, _Handle() as sync):
                with transaction():
                    event_store.append(event, stream_id=stream_id)
                    # TODO: SQLAlchemy is going to need flush.
                    #   In Django there is no UoW pattern.
                    sync.wait_to_commit()
            case Command.STOP:
                break
            case _:
                pass


class OtherClient:
    def __init__(
        self,
        event_store_factory: BackendFactory,
        transaction: Callable[[], ContextManager],
    ) -> None:
        self._inbox = Inbox()
        self._thread = Thread(
            target=agent,
            kwargs={
                "event_store_factory": event_store_factory,
                "transaction": transaction,
                "inbox": self._inbox,
            },
            daemon=True,
        )
        self._thread.start()

    def appends_in_transaction(self, event: Metadata, stream_id: StreamId) -> Handle:
        return self._inbox.put_event_to_append(event, stream_id)

    def stop(self) -> None:
        self._inbox.put_stop()
