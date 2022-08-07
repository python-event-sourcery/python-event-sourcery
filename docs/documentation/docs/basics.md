# Basics

## What is an event?
An event is a change of state. It is a piece of information stating a fact with extra information, letting to say what just actually happened and, potentially, react to it.

Since events merely state the fact, that something happened, we write them in past tense.

!!! example "Examples"

    Sprint started

    Payment failed

    Order cancelled

    Invoice issued

You can stop reading for a moment and think about examples from the projects you're working on.

When an event occurs it cannot be denied anymore. It can be only reacted to. Let's say that the payment failed but for some reason it should not. We can not negate the event, but we can always try to e.g. pay with another payment card. This is an example of reacting to an event.

In an application that uses events explicitly, they will somehow be represented in the source code. They can be coded as simple data structures:
```python
@dataclass
class SprintStarted:
    when_started: datetime
    when_ends: datetime
    project_key: ProjectKey
```

### How Event Sourcery helps with using events?

Event Sourcery provides a simple base class that is currently using [Pydantic](https://pydantic-docs.helpmanual.io/). It brings all goodies of that library plus provides a few basic fields, like unique identifier of an event or timestamp of event creation.

```python
from event_sourcery import Event

class SprintStarted(Event):
    when_started: datetime
    when_ends: datetime
    project_key: ProjectKey


event = SprintStarted(
    when_started=datetime.now(),
    when_ends=datetime.now() + timedelta(days=7),
    project_key="PRO",
)
# SprintStarted(
#     uuid=UUID('48c3ecb1-2d58-4b99-b964-2fb9ccfba601'),
#     created_at=datetime.datetime(2022, 8, 7, 16, 56, 35, 719248),
#     metadata=Metadata(correlation_id=None, causation_id=None),
#     when_started=datetime.datetime(2022, 8, 7, 18, 56, 35, 719177),
#     when_ends=datetime.datetime(2022, 8, 14, 18, 56, 35, 719184),
#     project_key='PRO'
# )
```

Other baked-in feature includes tracing ids - correlation id and causation id, useful for tracking flows of events in the system. 

## What is Event-Driven Architecture?

Systems that use Event-Driven Architecture (or EDA in short) use events for connecting its parts. One part of the system publishes an event, letting all other interested parts know that something significant happened. In turn, these parts may trigger some action on their side.

This pattern is used with microservices publishing events via brokers, such as [RabbitMQ](https://www.rabbitmq.com/) or [Apache Kafka](https://kafka.apache.org/).

!!! example "Event-Driven Distributed App"

    <figure markdown>
        ![EDA example](../res/eda_example.png){ width="600" }
    </figure>

Integration with events is a pattern that makes publishing part of the system ignorant of other parts, so there's loose coupling between them. For example, `Order Service` does not have to know that `Payment Service` or `Invoice Service` even exists.

Another benefit from asynchronous, event-driven architecture is that even if something is temporarily wrong with `Payment Service`, system can still operate. Broker will receive messages and once `Payment Service` is back online, the process can continue.

The same integration method can be used in much simpler environments, e.g. monorepo applications. One doesn't need a broker right away.

### How Event Sourcery helps with that?

Event Sourcery provides implementation of Event Store and so-called Outbox. 

The former is a class to provide persistence of events while the Outbox makes sure they will be published eventually, even if there's something with the broker.

First thing is to ask Event Store to not only save the event, but also to put it in the Outbox. You can do it using `publish` method instead of `append`.
```python
an_event = SomeEvent(first_name="John")

# publish additionally puts an event in outbox
event_store.publish(stream_id=uuid4(), events=[an_event])
```

Then, one has to implement publishing mechanism - e.g. publishing to Kafka or RabbitMQ, depending on your stack. Event Sourcery does not provide this out of the box. What it does provide is `Outbox` class that accepts `publisher` argument to send the message.

```python
from event_sourcery import get_outbox

outbox = get_outbox(
    session=session,  # SQLAlchemy session
    # a function that receives published event and does something with it 
    publisher=lambda event: print(event), 
)
```

The last step is to run `Outbox` in a separate process, e.g. separate docker container in an infinite loop:

```python

while True:
    try:
        outbox.run_once()
        session.commit()
    except:
        session.rollback()
        logger.exception("Outbox processing failed")

    time.sleep(5)
```

## What is Event Sourcing?

Recall any entity/model/being from a piece of software you recently worked on. Let's consider e-commerce `Order`. It might hold current status (new, confirmed, shipped, etc) and summaries – total price, shipping and taxes. 

Naturally, `Order` does not exist on its own. We usually wire it with another entity, `OrderLine`, that refers to a single product ordered with a quantity information. This structure could be represented in a relational database in a following way:

`orders`

| id | status | total_price |
| -- | ------ | ----------- |
|  1 |    new |      169.99 |

`order_lines`

| id | order_id | product_id | quantity |
| -- | -------- | ---------- | -------- |
|  1 |        1 |        512 |        1 |
|  2 |        1 |        614 |        3 |

By storing data this way we can always cheaply get **CURRENT** state of our `Order`. We store a dump of serialized object after latest changes. Changing anything, for example switching status from new to shipped causes data overwrite. **We irreversibly lose old state.**

What if we need to track all changes? Let’s see how that fits in another database table:

`order_history`

| id | order_id |    event_name |            datetime |                               data |
| -- | -------- | ------------- | ------------------- | ---------------------------------- |
|  1 |        1 |  OrderCreated | 2018-01-20 18:33:12 |                                    |
|  2 |        1 |     LineAdded | 2018-01-20 18:33:44 | {"product_id": 512, "quantity": 1} |
|  3 |        1 | StatusChanged | 2018-01-20 18:42:59 |            {"status": "confirmed"} |

Such a representation enables us to confidently say what was changed and when. But this `order_history` table plays only a second fiddle. It is merely an extra record of `Order`, added just to fulfill some business requirement. We still reach to original `orders` table when we want to know exact state of any Order in all other scenarios.

However, notice that `order_history` is as good as `orders` table when we have to get current `Order` state. How so? We just have to fetch all entries for given `Order` and _replay_ them from the start.

In the end we’ll get exactly the same information that is saved in `orders` table. So do we even need `orders` and `orders_lines` table as a source of truth...?

Event Sourcing proposes we don't. We can still keep them around to optimize reading data for UI, but no longer have to rely on it in any situation that would actually change `Order`.

To sum up, Event Sourcing comes down to:

- Keeping your business objects (called aggregates) as a series of replayable events.
- This is often called an event stream.
- Never deleting any events from a system, only appending new ones
- Using events as the only reliable way of telling in what state a given aggregate is
- If you need to query data or present them in a table-like format, keep a copy of them in a denormalized format. This is called projection
- Designing your aggregates to protect certain vital business invariants, such as Order encapsulates costs summary.
- A good rule of thumb is to keep aggregates as small as possible

### How Event Sourcery helps with that?

Event Sourcery provides a base class for an aggregate and repository implementation that makes it much easy to create or read/change aggregates.

```python
class LightSwitch(Aggregate):
    """A simple aggregate that models a light switch."""
    class AlreadyTurnedOn(Exception):
        pass

    class AlreadyTurnedOff(Exception):
        pass

    def __init__(
        self, past_events: list[Event], changes: list[Event], stream_id: StreamId
    ) -> None:
        # init any state you need in aggregate class to check conditions
        self._shines = False

        # required for base class
        super().__init__(past_events, changes, stream_id)

    def _apply(self, event: Event) -> None:
        # each aggregate need an _apply method to parse events
        match event:
            case TurnedOn() as event:
                self._shines = True
            case TurnedOff() as event:
                self._shines = False

    def turn_on(self) -> None:
        # this is one of command methods
        # we can rejest it (i.e. raise an exception)
        # if current state does not allow this to proceed
        # e.g. light is already on
        if self._shines:
            raise LightSwitch.AlreadyTurnedOn
        self._event(TurnedOn)

    def turn_off(self) -> None:
        if not self._shines:
            raise LightSwitch.AlreadyTurnedOff

        self._event(TurnedOff)
```

To create a `Repository` tailored for a particular Aggregate class, we need  that class and `Event Store` instance: 

```python
repository = Repository[LightSwitch](event_store, LightSwitch)
```

A `Repository` exposes method to create a new instance of Aggregate:

```python
stream_id = uuid4()

with repository.new(stream_id=stream_id) as switch:
    switch.turn_on()
```

...or to work with existing Aggregate, making sure changes are saved at the end:

```python
with repository.aggregate(stream_id=stream_id) as switch_second_incarnation:
    try:
        switch_second_incarnation.turn_on()
    except LightSwitch.AlreadyTurnedOn:
        # o mon Dieu, I made a mistake!
        switch_second_incarnation.turn_off()
```

A `Repository` is a thin wrapper over Event Store. One can also write Aggregates even without using our base class and use `EventStore` directly!
