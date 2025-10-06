from kurrentdbclient import KurrentDBClient

from event_sourcery.event_store.types import StreamId
from event_sourcery_kurrentdb import KurrentDBBackend

client = KurrentDBClient(uri="kurrentdb://localhost:2113?Tls=false")
backend = KurrentDBBackend().configure(client)
backend.event_store.load_stream(StreamId())  # test if connection works
