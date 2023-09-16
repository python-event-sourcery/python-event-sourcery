from typing import Any
from unittest.mock import ANY
from uuid import UUID

from event_sourcery import Metadata
from event_sourcery.repository import TEvent


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
