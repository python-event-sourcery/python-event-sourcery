__all__ = [
    "BaseEvent",
    "BaseOutboxEntry",
    "BaseProjectorCursor",
    "BaseSnapshot",
    "BaseStream",
    "Config",
    "SQLAlchemyBackend",
    "SqlAlchemyStorageStrategy",
    "configure_models",
    "models",
]

from datetime import timedelta

from pydantic import BaseModel, ConfigDict, PositiveInt
from sqlalchemy.orm import Session
from typing_extensions import Self

from event_sourcery.event_store import Dispatcher, TransactionalBackend
from event_sourcery.event_store.backend import no_filter, not_configured
from event_sourcery.event_store.interfaces import (
    OutboxFiltererStrategy,
    OutboxStorageStrategy,
    StorageStrategy,
    SubscriptionStrategy,
)
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


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_attempts: PositiveInt = 3
    gap_retry_interval: timedelta = timedelta(seconds=0.5)


class SQLAlchemyBackend(TransactionalBackend):
    UNCONFIGURED_MESSAGE = "Configure backend with `.configure(session, config)`"

    def __init__(self) -> None:
        super().__init__()
        self[BaseEvent] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[BaseStream] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[BaseSnapshot] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[BaseOutboxEntry] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[Session] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[Config] = not_configured(self.UNCONFIGURED_MESSAGE)
        self[StorageStrategy] = lambda c: SqlAlchemyStorageStrategy(
            c[Session],
            c[Dispatcher],
            c.get(SqlAlchemyOutboxStorageStrategy, None),
            c[BaseEvent],
            c[BaseSnapshot],
            c[BaseStream],
        ).scoped_for_tenant(c.tenant_id)
        self[SubscriptionStrategy] = lambda c: SqlAlchemySubscriptionStrategy(
            c[Session],
            c[Config].gap_retry_interval,
            c[BaseEvent],
            c[BaseStream],
        )

    def configure(
        self,
        session: Session,
        config: Config | None = None,
        event_model: type[BaseEvent] = DefaultEvent,
        stream_model: type[BaseStream] = DefaultStream,
        snapshot_model: type[BaseSnapshot] = DefaultSnapshot,
        outbox_entry_model: type[BaseOutboxEntry] = DefaultOutboxEntry,
    ) -> Self:
        self[Session] = session
        self[Config] = config or Config()
        self[BaseEvent] = lambda _: event_model
        self[BaseStream] = lambda _: stream_model
        self[BaseSnapshot] = lambda _: snapshot_model
        self[BaseOutboxEntry] = lambda _: outbox_entry_model
        return self

    def with_outbox(self, filterer: OutboxFiltererStrategy = no_filter) -> Self:
        self[OutboxFiltererStrategy] = filterer
        self[SqlAlchemyOutboxStorageStrategy] = (
            lambda c: SqlAlchemyOutboxStorageStrategy(
                c[Session],
                c[OutboxFiltererStrategy],
                c[Config].outbox_attempts,
                c[BaseOutboxEntry],
            )
        )
        self[OutboxStorageStrategy] = lambda c: c[SqlAlchemyOutboxStorageStrategy]
        return self
