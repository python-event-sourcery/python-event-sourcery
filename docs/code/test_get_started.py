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

    for recorded in event_store.load_stream(StreamId(name="invoices/1003")):
        print(recorded.event, recorded.version)
    # --8<-- [end:get_started_01]

    events = event_store.load_stream(StreamId(name="invoices/1003"))
    assert len(events) == 1
    assert events[0].event.invoice_number == "1003"
    assert events[0].version == 1
