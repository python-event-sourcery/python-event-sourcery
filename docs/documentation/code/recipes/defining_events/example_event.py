from event_sourcery.event_store import Event


class InvoicePaid(Event):
    invoice_number: str
