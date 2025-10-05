from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from functools import wraps
from typing import NoReturn, TypeVar, cast

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


T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)

_Provider = Callable[["_Container"], T]


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


class _Container:
    def __init__(self) -> None:
        self.providers: dict[type, _Provider] = {}

    def __getitem__(self, _type: type[T]) -> T:
        return cast(_Provider[T], self.providers[_type])(self)

    def __setitem__(self, _type: type[T], value: T | _Provider[T]) -> None:
        self.providers[_type] = (
            cast(_Provider[T], lambda _: value)
            if isinstance(value, _type)
            else cast(_Provider[T], value)
        )

    def get(self, _type: type[T], default: T | None = None) -> T | None:
        if _type not in self.providers:
            return default
        return self[_type]

    def copy(self) -> Self:
        new: Self = self.__class__()
        new.providers.update(self.providers.copy())
        return new


class Backend(_Container):
    def __init__(self) -> None:
        super().__init__()
        self[TenantId] = DEFAULT_TENANT
        self[EventRegistry] = EventRegistry()
        self[EncryptionStrategy] = NoEncryptionStrategy()
        self[EncryptionKeyStorageStrategy] = (
            lambda c: NoKeyStorageStrategy().scoped_for_tenant(c[TenantId])
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
        return self[EventStore]

    @property
    def outbox(self) -> Outbox:
        return self[Outbox]

    @property
    def subscriber(self) -> subscription.PositionPhase:
        return self[subscription.PositionPhase]

    def in_tenant_mode(self, tenant_id: TenantId) -> Self:
        in_tenant_mode = self.copy()
        in_tenant_mode[TenantId] = tenant_id
        return in_tenant_mode

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        raise NotImplementedError()

    def with_encryption(
        self,
        strategy: EncryptionStrategy,
        key_storage: EncryptionKeyStorageStrategy,
    ) -> Self:
        self[EncryptionStrategy] = strategy
        self[EncryptionKeyStorageStrategy] = lambda c: key_storage.scoped_for_tenant(
            c[TenantId],
        )
        return self


class TransactionalBackend(Backend):
    def __init__(self) -> None:
        super().__init__()
        self[Listeners] = singleton(lambda _: Listeners())
        self[Dispatcher] = lambda c: Dispatcher(c[Serde], c[Listeners])

    @property
    def in_transaction(self) -> Listeners:
        return cast(Listeners, self[Listeners])
