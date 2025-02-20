from event_sourcery.event_store import EventStore  # noqa
from ._common import session
from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory

factory = SQLAlchemyBackendFactory(session)
backend = factory.build()
backend.event_store
assert backend.event_store is EventStore
