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
    event_model: type[BaseEvent]
    stream_model: type[BaseStream]
    snapshot_model: type[BaseSnapshot]
    outbox_entry_model: type[BaseOutboxEntry] = DefaultOutboxEntry


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_attempts: PositiveInt = 3
    gap_retry_interval: timedelta = timedelta(seconds=0.5)


class SQLAlchemyBackend(TransactionalBackend):
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
