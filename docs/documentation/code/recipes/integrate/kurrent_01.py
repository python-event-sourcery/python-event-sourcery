from kurrentdbclient import KurrentDBClient

from event_sourcery.event_store import StreamId
from event_sourcery_kurrentdb import KurrentDBBackendFactory

client = KurrentDBClient(uri="kurrentdb://localhost:2113?Tls=false")
factory = KurrentDBBackendFactory(client)
backend = factory.build()
backend.event_store.load_stream(StreamId())  # test if connection works
