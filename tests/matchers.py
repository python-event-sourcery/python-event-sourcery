from typing import Any, TypeVar
from unittest.mock import ANY
from uuid import UUID

from event_sourcery.event_store import Event, Metadata

TEvent = TypeVar("TEvent", bound=Event)


class AnyUUID:
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, UUID)


def any_metadata(for_event: TEvent) -> Metadata[TEvent]:
    return Metadata[TEvent].construct(
        event=for_event,
        version=ANY,
        uuid=ANY,
        created_at=ANY,
        context=ANY,
    )
