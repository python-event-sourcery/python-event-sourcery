__all__ = [
    "configure_models",
    "get_event_store",
    "Event",
]

from sqlalchemy.orm import Session

from event_sourcery.event_store import EventStore
from event_sourcery_pydantic.event import Event
from event_sourcery_pydantic.serde import PydanticSerde
from event_sourcery_sqlalchemy.models import configure_models
from event_sourcery_sqlalchemy.sqlalchemy_event_store import SqlAlchemyStorageStrategy


def get_event_store(session: Session) -> EventStore:
    return EventStore(
        serde=PydanticSerde(),
        storage_strategy=SqlAlchemyStorageStrategy(session),
        event_base_class=Event,
    )
