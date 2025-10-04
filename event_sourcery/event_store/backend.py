import abc
from collections import UserDict
from collections.abc import Iterator
from contextlib import AbstractContextManager
from functools import wraps
from typing import NoReturn, Protocol, TypeVar, cast

from typing_extensions import Self

from event_sourcery.event_store import subscription
from event_sourcery.event_store.dispatcher import Dispatcher, Listeners
from event_sourcery.event_store.event import (
    Encryption,
    EventRegistry,
    NoEncryptionStrategy,
    NoKeyStorageStrategy,
    RawEvent,
    RecordedRaw,
    Serde,
)
from event_sourcery.event_store.event_store import EventStore
from event_sourcery.event_store.interfaces import (
    EncryptionKeyStorageStrategy,
    EncryptionStrategy,
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
    StorageStrategy,
    SubscriptionStrategy,
)
from event_sourcery.event_store.outbox import Outbox
from event_sourcery.event_store.tenant_id import DEFAULT_TENANT, TenantId


class NoProviderConfigured(Exception):
    pass


def no_filter(entry: RawEvent) -> bool:
    return True


class NoOutboxStorageStrategy(OutboxStorageStrategy):
    def outbox_entries(
        self, limit: int
    ) -> Iterator[AbstractContextManager[RecordedRaw]]:
        return iter([])


T_co = TypeVar("T_co", covariant=True)
T = TypeVar("T")


class _Provider(Protocol[T_co]):
    def __call__(self, container: "_Container") -> T_co: ...


def singleton(provider: _Provider[T]) -> _Provider[T]:
    result: T | None = None

    @wraps(provider)
    def _wrapper(container: "_Container") -> T:
        nonlocal result
        if result is not None:
            return result
        result = provider(container)
        return result

    return _wrapper


def not_configured(error_message: str) -> _Provider[T]:
    def _raise(container: "_Container") -> NoReturn:
        raise NoProviderConfigured(error_message)  # pragma: no cover

    return _raise


class _Container(UserDict[type[T], _Provider[T] | T]):
    def __getitem__(self, _type: type[T]) -> T:
        provider = cast(_Provider[T], self.data[_type])
        return provider(self)

    def __setitem__(self, _type: type[T], value: T | _Provider[T]) -> None:
        self.data[_type] = (
            cast(_Provider[T], lambda _: value) if isinstance(value, _type) else value
        )

    def copy(self) -> Self:
        new: Self = self.__class__()
        new.data.update(self.data.copy())
        return new


class Backend(_Container):
    tenant_id: TenantId

    def __init__(self) -> None:
        super().__init__()
        self.tenant_id = DEFAULT_TENANT
        self[EventRegistry] = lambda _: EventRegistry()
        self[EncryptionStrategy] = lambda _: NoEncryptionStrategy()
        self[EncryptionKeyStorageStrategy] = (
            lambda c: NoKeyStorageStrategy().scoped_for_tenant(c.tenant_id)
        )
        self[Encryption] = lambda c: Encryption(
            registry=c[EventRegistry],
            strategy=c[EncryptionStrategy],
            key_storage=c[EncryptionKeyStorageStrategy],
        )
        self[Serde] = lambda c: Serde(
            registry=c[EventRegistry],
            encryption=c[Encryption],
        )
        self[StorageStrategy] = not_configured(
            "Use one of pyES backends: SQLAlchemy, Django or KurrentDB",
        )
        self[EventStore] = lambda c: EventStore(
            storage_strategy=c[StorageStrategy],
            serde=c[Serde],
        )
        self[Outbox] = lambda c: Outbox(
            strategy=c[OutboxStorageStrategy],
            serde=c[Serde],
        )
        self[OutboxStorageStrategy] = lambda _: NoOutboxStorageStrategy()
        self[SubscriptionStrategy] = not_configured(
            "Use one of pyES backends: SQLAlchemy, Django or KurrentDB",
        )
        self[subscription.PositionPhase] = lambda c: subscription.SubscriptionBuilder(
            c[Serde],
            c[SubscriptionStrategy],
        )

    @property
    def event_store(self) -> EventStore:
        return cast(EventStore, self[EventStore])

    @property
    def outbox(self) -> Outbox:
        return cast(Outbox, self[Outbox])

    @property
    def subscriber(self) -> subscription.PositionPhase:
        return cast(subscription.PositionPhase, self[subscription.PositionPhase])

    def in_tenant_mode(self, tenant_id: TenantId) -> Self:
        in_tenant_mode = self.copy()
        in_tenant_mode.tenant_id = tenant_id
        return in_tenant_mode

    @abc.abstractmethod
    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self: ...

    def with_encryption(
        self,
        strategy: EncryptionStrategy,
        key_storage: EncryptionKeyStorageStrategy,
    ) -> Self:
        self[EncryptionStrategy] = strategy
        self[EncryptionKeyStorageStrategy] = lambda c: key_storage.scoped_for_tenant(
            c.tenant_id
        )
        return self


class TransactionalBackend(Backend, abc.ABC):
    def __init__(self) -> None:
        super().__init__()
        self[Listeners] = singleton(lambda _: Listeners())
        self[Dispatcher] = lambda c: Dispatcher(c[Serde], c[Listeners])

    @property
    def in_transaction(self) -> Listeners:
        return cast(Listeners, self[Listeners])
