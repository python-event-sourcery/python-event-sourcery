__all__ = [
    "BaseEvent",
    "BaseOutboxEntry",
    "BaseProjectorCursor",
    "BaseSnapshot",
    "BaseStream",
    "Config",
    "Models",
    "SQLAlchemyBackend",
    "SqlAlchemyStorageStrategy",
    "configure_models",
    "models",
]

from dataclasses import dataclass
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, PositiveInt
from sqlalchemy.orm import Session
from typing_extensions import Self

from event_sourcery.event_store.backend import (
    TenantId,
    TransactionalBackend,
    not_configured,
)
from event_sourcery.event_store.in_transaction import Dispatcher
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
    StorageStrategy,
    SubscriptionStrategy,
)
from event_sourcery.event_store.outbox import no_filter
from event_sourcery_sqlalchemy import models
from event_sourcery_sqlalchemy.event_store import SqlAlchemyStorageStrategy
from event_sourcery_sqlalchemy.models import configure_models
from event_sourcery_sqlalchemy.models.base import (
    BaseEvent,
    BaseOutboxEntry,
    BaseProjectorCursor,
    BaseSnapshot,
    BaseStream,
)
from event_sourcery_sqlalchemy.models.default import (
    DefaultEvent,
    DefaultOutboxEntry,
    DefaultSnapshot,
    DefaultStream,
)
from event_sourcery_sqlalchemy.outbox import SqlAlchemyOutboxStorageStrategy
from event_sourcery_sqlalchemy.subscription import SqlAlchemySubscriptionStrategy


@dataclass(frozen=True)
class Models:
    """
    Container for SQLAlchemy ORM models used by the backend.

    Allows customization of the event, stream, snapshot, and outbox entry models used by
    the backend. It allows to have different event store models for different modules in
    modular monolith applications still having in transactional event dispatching
    between them.

    By default, uses the standard models provided by Event Sourcery.

    Attributes:
        event_model (type[BaseEvent]): SQLAlchemy model for events.
        stream_model (type[BaseStream]): SQLAlchemy model for streams.
        snapshot_model (type[BaseSnapshot]): SQLAlchemy model for snapshots.
        outbox_entry_model (type[BaseOutboxEntry]):
            SQLAlchemy model for outbox entries (default: DefaultOutboxEntry).
    """

    event_model: type[BaseEvent]
    stream_model: type[BaseStream]
    snapshot_model: type[BaseSnapshot]
    outbox_entry_model: type[BaseOutboxEntry] = DefaultOutboxEntry


class Config(BaseModel):
    """
    Configuration for SQLAlchemyBackend event store integration.

    Attributes:
        outbox_attempts (PositiveInt):
            Maximum number of outbox delivery attempts per event before giving up.
        gap_retry_interval (timedelta):
            Time to wait before retrying a subscription gap. If the subscription detects a gap in event identifiers (e.g., missing event IDs),
            it assumes there may be an open transaction and the database has already assigned IDs for new events that are not yet committed.
            This interval determines how long the subscription waits before retrying to fetch events, preventing loss of events that are in the process of being written to the database.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_attempts: PositiveInt = 3
    gap_retry_interval: timedelta = timedelta(seconds=0.5)


class SQLAlchemyBackend(TransactionalBackend):
    """
    SQLAlchemy integration backend for Event Sourcery.
    """

    UNCONFIGURED_MESSAGE = "Configure backend with `.configure(session, config)`"

    def __init__(self) -> None:
        super().__init__()
        self[Models] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[Session] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[Config] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[StorageStrategy] = lambda c: SqlAlchemyStorageStrategy(
            c[Session],
            c[Dispatcher],
            c.get(SqlAlchemyOutboxStorageStrategy, None),
            c[Models].event_model,
            c[Models].snapshot_model,
            c[Models].stream_model,
        ).scoped_for_tenant(c[TenantId])
        self[SubscriptionStrategy] = lambda c: SqlAlchemySubscriptionStrategy(
            c[Session],
            c[Config].gap_retry_interval,
            c[Models].event_model,
            c[Models].stream_model,
        )

    def configure(
        self,
        session: Session,
        config: Config | None = None,
        custom_models: Models | None = None,
    ) -> Self:
        """
        Sets the backend configuration for SQLAlchemy session, outbox, and models.

        Allows you to provide a SQLAlchemy Session instance, an optional Config
        instance, and optional custom ORM models.
        If no config or models are provided, the default configuration and models are
        used.
        This method must be called before using the backend in production to ensure
        correct event publishing and subscription reliability.

        Args:
            session (Session): The SQLAlchemy session instance to use for backend operations.
            config (Config | None): Optional custom configuration. If None, uses default Config().
            custom_models (Models | None): Optional custom ORM models. If None, uses default models.

        Returns:
            Self: The configured backend instance (for chaining).
        """

        if custom_models is None:
            custom_models = Models(
                event_model=DefaultEvent,
                stream_model=DefaultStream,
                snapshot_model=DefaultSnapshot,
                outbox_entry_model=DefaultOutboxEntry,
            )

        self[Session] = session
        self[Config] = config or Config()
        self[Models] = custom_models
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self[OutboxFiltererStrategy] = filterer  # type: ignore[type-abstract]
        self[SqlAlchemyOutboxStorageStrategy] = (
            lambda c: SqlAlchemyOutboxStorageStrategy(
                c[Session],
                c[OutboxFiltererStrategy],  # type: ignore[type-abstract]
                c[Config].outbox_attempts,
                c[Models].outbox_entry_model,
            )
        )
        self[OutboxStorageStrategy] = lambda c: c[SqlAlchemyOutboxStorageStrategy]
        return self
