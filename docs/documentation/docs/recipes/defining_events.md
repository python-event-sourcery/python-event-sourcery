To define an event, write a class inheriting from [Event](/reference/event/) base class.

// TODO: include it from elsewhere to make sure this code is working
// ...and is formatted plus linted etc

```python
from event_sourcery.event_store import Event


class InvoicePaid(Event):
    invoice_number: str
```
