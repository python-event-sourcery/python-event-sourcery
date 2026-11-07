def test_get_started():
    # --8<-- [start:get_started_01]
    from event_sourcery import StreamId
    from event_sourcery.backend import InMemoryBackend
    from event_sourcery.event import Event

    class InvoicePaid(Event):
        invoice_number: str

    backend = InMemoryBackend()
    event_store = backend.event_store

    event_store.append(
        InvoicePaid(invoice_number="1003"),
        stream_id=StreamId(name="invoices/1003"),
    )
    # --8<-- [end:get_started_01]
    # --8<-- [start:get_started_02]
    recorded_events = event_store.load_stream(StreamId(name="invoices/1003"))
    for recorded in recorded_events:
        print(recorded.event, recorded.version)
    # --8<-- [end:get_started_02]

    events = event_store.load_stream(StreamId(name="invoices/1003"))
    assert len(events) == 1
    assert events[0].event.invoice_number == "1003"
    assert events[0].version == 1


def test_get_started_async():
    # --8<-- [start:get_started_async_01]
    import asyncio

    from event_sourcery import StreamId
    from event_sourcery.async_.backend import AsyncInMemoryBackend
    from event_sourcery.event import Event

    class InvoicePaid(Event):
        invoice_number: str

    backend = AsyncInMemoryBackend()
    event_store = backend.event_store

    async def main() -> None:
        await event_store.append(
            InvoicePaid(invoice_number="1003"),
            stream_id=StreamId(name="invoices/1003"),
        )

    asyncio.run(main())

    # --8<-- [end:get_started_async_01]
    # --8<-- [start:get_started_async_02]
    async def read() -> None:
        recorded_events = await event_store.load_stream(
            StreamId(name="invoices/1003"),
        )
        for recorded in recorded_events:
            print(recorded.event, recorded.version)

    asyncio.run(read())
    # --8<-- [end:get_started_async_02]

    events = asyncio.run(event_store.load_stream(StreamId(name="invoices/1003")))
    assert len(events) == 1
    assert events[0].event.invoice_number == "1003"
    assert events[0].version == 1
