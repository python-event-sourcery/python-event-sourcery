from esdbclient import EventStoreDBClient

from event_sourcery.event_store import StreamId
from event_sourcery_esdb import ESDBBackendFactory

client = EventStoreDBClient(uri="esdb://localhost:2113?Tls=false")
factory = ESDBBackendFactory(client)
backend = factory.build()
backend.event_store.load_stream(StreamId())  # test if connection works
