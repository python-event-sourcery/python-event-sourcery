from collections.abc import Callable
from typing import TypeAlias

from event_sourcery.event_store import Event, EventStore, Metadata, StreamId
from event_sourcery.read_model.cursors_dao import CursorsDao

ReadModel: TypeAlias = Callable[[Metadata, StreamId], None]


class Projector:
    class CantProjectUnversionedEvent(Exception):
        pass

    def __init__(
        self,
        event_store: EventStore,
        name: str,
        cursors_dao: CursorsDao,
        read_model: ReadModel,
    ) -> None:
        self._event_store = event_store
        self._name = name
        self._cursors_dao = cursors_dao
        self._read_model = read_model

    def project(self, metadata: Metadata[Event], stream_id: StreamId) -> None:
        if metadata.version is None:
            raise self.CantProjectUnversionedEvent

        try:
            self._cursors_dao.increment(
                name=self._name, stream_id=stream_id, version=metadata.version
            )
            self._read_model(metadata, stream_id)
        except self._cursors_dao.StreamNotTracked:
            self._cursors_dao.put_at(
                name=self._name, stream_id=stream_id, version=metadata.version
            )
            missed_events = self._event_store.load_stream(
                stream_id=stream_id, stop=metadata.version
            )
            for event in missed_events:
                self._read_model(event, stream_id)

            self._read_model(metadata, stream_id)
        except self._cursors_dao.BehindStream as exc:
            self._cursors_dao.move_to(
                name=self._name, stream_id=stream_id, version=metadata.version
            )
            missed_events = self._event_store.load_stream(
                stream_id=stream_id,
                start=exc.current_version + 1,
                stop=metadata.version,
            )
            for event in missed_events:
                self._read_model(event, stream_id)

            self._read_model(metadata, stream_id)
        except self._cursors_dao.AheadOfStream:
            return
