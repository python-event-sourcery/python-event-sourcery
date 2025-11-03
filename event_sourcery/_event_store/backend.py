from collections.abc import Callable
from functools import wraps
from typing import NoReturn, TypeVar, cast

from typing_extensions import Self

from event_sourcery._event_store.event.encryption import (
    Encryption,
    EncryptionKeyStorageStrategy,
    EncryptionStrategy,
    NoEncryptionStrategy,
    NoKeyStorageStrategy,
)
from event_sourcery._event_store.event.registry import EventRegistry
from event_sourcery._event_store.event.serde import Serde
from event_sourcery._event_store.event_store import (
    EventStore,
    StorageStrategy,
)
from event_sourcery._event_store.outbox import (
    NoOutboxStorageStrategy,
    Outbox,
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
    no_filter,
)
from event_sourcery._event_store.subscription.builder import (
    SubscriptionBuilder,
)
from event_sourcery._event_store.subscription.in_transaction import (
    Dispatcher,
    Listeners,
)
from event_sourcery._event_store.subscription.interfaces import (
    PositionPhase,
    SubscriptionStrategy,
)
from event_sourcery._event_store.tenant_id import DEFAULT_TENANT, TenantId
from event_sourcery.exceptions import NoProviderConfigured

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)

_Provider = Callable[["_Container"], T]


def singleton(provider: _Provider[T]) -> _Provider[T]:
    """
    Decorator that ensures the provider returns the same instance (singleton)
    for every call within the container's lifecycle.

    Args:
        provider (_Provider[T]): The provider function to wrap.

    Returns:
        _Provider[T]: A provider that always returns the same instance.
    """
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
    """
    Used as a placeholder for providers that require configuration.

    Args:
        error_message (str): str. The error message to raise with the exception.
    """

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
    """
    Dependency Injection container for Event Sourcery components.

    Dict-like object resolving object instance during access by type.
    Providers are passed setting the type as key and provider as a value.

    By default, basic implementations are registered or an exception is raised
    if backend configuration (e.g., storage strategy) is required.

    Core components are exposed by properties.
    """

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
        self[PositionPhase] = lambda c: SubscriptionBuilder(
            c[Serde],
            c[SubscriptionStrategy],
        )

    @property
    def event_store(self) -> EventStore:
        """
        Returns the current instance of `EventStore`.
        """
        return self[EventStore]

    @property
    def outbox(self) -> Outbox:
        """
        Returns the current instance of `Outbox`.
        """
        return self[Outbox]

    @property
    def subscriber(self) -> PositionPhase:
        """
        Returns the current instance of `SubscriptionBuilder` (as `PositionPhase`).
        """
        return self[PositionPhase]

    def in_tenant_mode(self, tenant_id: TenantId) -> Self:
        """
        Returns a copy of the backend with the specified tenant ID set.
        """
        in_tenant_mode = self.copy()
        in_tenant_mode[TenantId] = tenant_id
        return in_tenant_mode

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        """
        Configure the outbox with a custom filter.
        """
        raise NotImplementedError()

    def with_encryption(
        self,
        strategy: EncryptionStrategy,
        key_storage: EncryptionKeyStorageStrategy,
    ) -> Self:
        """
        Configures event encryption with the provided strategy and key storage.
        """
        self[EncryptionStrategy] = strategy
        self[EncryptionKeyStorageStrategy] = lambda c: key_storage.scoped_for_tenant(
            c[TenantId],
        )
        return self


class TransactionalBackend(Backend):
    """
    Backend variant that provides transactional event handling support.

    Registers additional services for managing listeners and dispatchers
    to enable in-transaction event processing.

    Properties:
        in_transaction (Listeners): The current state of in transaction Listeners.
    """

    def __init__(self) -> None:
        super().__init__()
        self[Listeners] = singleton(lambda _: Listeners())
        self[Dispatcher] = lambda c: Dispatcher(c[Serde], c[Listeners])

    @property
    def in_transaction(self) -> Listeners:
        """
        Returns the current instance of `Listeners` for transactional event handling.
        """
        return cast(Listeners, self[Listeners])
