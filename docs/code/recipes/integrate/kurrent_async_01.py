import asyncio

from kurrentdbclient import AsyncKurrentDBClient

from event_sourcery import StreamId
from event_sourcery_kurrentdb.async_ import AsyncKurrentDBBackend


async def main() -> None:
    client = AsyncKurrentDBClient(uri="kurrentdb://localhost:2113?Tls=false")
    backend = AsyncKurrentDBBackend().configure(client)
    await backend.event_store.load_stream(StreamId())  # test if connection works


asyncio.run(main())
