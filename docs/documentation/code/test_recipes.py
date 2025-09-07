import typing
from concurrent.futures import Future
from datetime import datetime

import pika
import pytest
import time_machine

from event_sourcery.event_sourcing import Aggregate, Repository
from event_sourcery.event_store import Recorded, StreamId, WrappedEvent

if typing.TYPE_CHECKING:
    from event_sourcery.event_store import Event


@pytest.fixture(scope="session", autouse=True)
def event_cls() -> type["Event"]:
    # --8<-- [start:defining_events_01]
    from event_sourcery.event_store import Event

    class InvoicePaid(Event):
        invoice_number: str

    # --8<-- [end:defining_events_01]
    return InvoicePaid


@pytest.fixture(scope="session", autouse=True)
def base_with_configured_es_models():
    from sqlalchemy.orm import declarative_base

    Base = declarative_base()
    # --8<-- [start:integrate_sql_00]
    from event_sourcery_sqlalchemy import configure_models

    configure_models(Base)  # Base is your declarative base class
    # --8<-- [end:integrate_sql_00]
    return Base


def test_sqlalchemy_backend(base_with_configured_es_models):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    Base = base_with_configured_es_models
    Base.metadata.create_all(engine)
    # --8<-- [start:integrate_sql_01]
    from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory

    session = Session()  # SQLAlchemy session
    factory = SQLAlchemyBackendFactory(session)
    backend = factory.build()
    # --8<-- [end:integrate_sql_01]
    # --8<-- [start:integrate_sql_02]
    backend.event_store
    # --8<-- [end:integrate_sql_02]
    assert backend.event_store.position == 0


def test_kurrent_db():
    pass
    # from kurrentdb import KurrentDBClient
    # from event_sourcery_kurrentdb import KurrentDBBackendFactory
    #
    # client = KurrentDBClient(uri="kurrentdb://localhost:2113?Tls=false")
    # factory = KurrentDBBackendFactory(client)
    # backend = factory.build()


@time_machine.travel(datetime(2025, 3, 16, 10, 3, 2, 138667), tick=False)
def test_saving(event_cls: type["Event"], base_with_configured_es_models):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory

    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    Base = base_with_configured_es_models

    Base.metadata.create_all(engine)
    factory = SQLAlchemyBackendFactory(Session())
    event_store = factory.build().event_store
    InvoicePaid = event_cls

    # --8<-- [start:saving_events_01]
    invoice_paid = InvoicePaid(invoice_number="1003")
    stream_id = StreamId(name="invoices/1003")
    event_store.append(invoice_paid, stream_id=stream_id)
    # --8<-- [end:saving_events_01]
    # --8<-- [start:saving_events_02]
    events = event_store.load_stream(stream_id)
    # [
    #   WrappedEvent(
    #       event=InvoicePaid(invoice_number='1003'),
    #       version=1,
    #       uuid=UUID('831cd32b-02b9-48d2-a67c-28cf7dbb37fa'),
    #       created_at=datetime.datetime(2025, 3, 16, 10, 3, 2, 138667),
    #       context=Context(correlation_id=None, causation_id=None)
    #   )
    # ]
    # --8<-- [end:saving_events_02]
    # TODO
    # assert repr(events) == "[WrappedEvent(event=InvoicePaid(invoice_number='1003'), version=1, uuid=UUID('831cd32b-02b9-48d2-a67c-28cf7dbb37fa'), created_at=datetime.datetime(2025, 3, 16, 10, 3, 2, 138667), context=Context(correlation_id=None, causation_id=None))]"
    assert len(events) == 1


def test_subscribing(event_cls: type["Event"], base_with_configured_es_models):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory

    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    Base = base_with_configured_es_models

    Base.metadata.create_all(engine)
    factory = SQLAlchemyBackendFactory(Session())
    backend = factory.build()
    InvoicePaid = event_cls

    invoice_paid = InvoicePaid(invoice_number="1004")
    stream_id = StreamId(name="invoices/1004")
    backend.event_store.append(invoice_paid, stream_id=stream_id)
    # --8<-- [start:subscriptions_01]
    subscription = (
        backend.subscriber.start_from(0)  # read from position 0...
        .to_events([InvoicePaid])  # ...InvoicePaid events...
        .build_iter(timelimit=1)  # ... iterate events one by one...
        # ...and wait up to 1 second for a new event
    )
    # --8<-- [end:subscriptions_01]
    # --8<-- [start:subscriptions_02]
    for recorded_event in subscription:
        if recorded_event is None:  # no more events for now
            break

        # process the event
        print(recorded_event.wrapped_event)
        print(recorded_event.position)
        print(recorded_event.tenant_id)
    # --8<-- [end:subscriptions_02]
    # --8<-- [start:subscriptions_03]
    batch_subscription = (
        backend.subscriber.start_from(0)
        .to_events([InvoicePaid])
        .build_batch(size=10, timelimit=1)  # try getting 10 events at a time
    )
    # --8<-- [end:subscriptions_03]
    # --8<-- [start:subscriptions_04]
    for batch in batch_subscription:
        # process the batch
        print(batch)
        if len(batch) == 0:  # no more events at the moment
            break
    # --8<-- [end:subscriptions_04]
    assert True


def test_outbox(
    event_cls: type["Event"],
    base_with_configured_es_models,
    request: pytest.FixtureRequest,
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory

    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    Base = base_with_configured_es_models

    Base.metadata.create_all(engine)
    session = Session()
    # --8<-- [start:outbox_01]
    factory = (
        SQLAlchemyBackendFactory(session).with_outbox()  # enable outbox
    )
    backend = factory.build()
    # --8<-- [end:outbox_01]
    # --8<-- [start:outbox_01_filterer]
    factory = SQLAlchemyBackendFactory(session).with_outbox(
        filterer=lambda e: "InvoicePaid" in e.name
    )
    backend = factory.build()
    # --8<-- [end:outbox_01_filterer]
    InvoicePaid = event_cls

    invoice_paid = InvoicePaid(invoice_number="an_invoice_number_outbox")
    stream_id = StreamId(name="invoices/1004")
    backend.event_store.append(invoice_paid, stream_id=stream_id)

    # --8<-- [start:outbox_02_pika]
    # setting up connection and queue...
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()
    channel.queue_declare(queue="events")
    # --8<-- [end:outbox_02_pika]

    request.addfinalizer(lambda: connection.close())

    # --8<-- [start:outbox_02_pika2]
    def publish(recorded: Recorded) -> None:
        as_json = recorded.wrapped_event.event.model_dump_json()
        channel.basic_publish(exchange="", routing_key="events", body=as_json)

    # --8<-- [end:outbox_02_pika2]

    # --8<-- [start:outbox_03]
    backend.outbox.run(publisher=publish)
    # --8<-- [end:outbox_03]

    # --8<-- [start:outbox_03a]
    backend.outbox.run(publisher=publish, limit=50)
    # --8<-- [end:outbox_03a]

    fut = Future()

    def callback(ch, method, properties, body):
        print(f"pika callback {locals()}")
        fut.set_result(body)
        ch.stop_consuming()  # this causes start_consuming blocking call below to stop

    channel.basic_consume(queue="events", auto_ack=True, on_message_callback=callback)
    channel.start_consuming()

    result: bytes = fut.result(timeout=2)
    assert "an_invoice_number_outbox" in result.decode()

    session.rollback()
    # --8<-- [start:outbox_04]
    with session.begin():
        backend.outbox.run(publisher=publish)
        session.commit()
    # --8<-- [end:outbox_04]


@pytest.fixture()
def sqlite_in_memory_backend(base_with_configured_es_models):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from event_sourcery_sqlalchemy import SQLAlchemyBackendFactory

    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    Base = base_with_configured_es_models

    Base.metadata.create_all(engine)
    factory = SQLAlchemyBackendFactory(Session())
    return factory.build()


def test_event_sourcing(sqlite_in_memory_backend) -> None:
    backend = sqlite_in_memory_backend
    # --8<-- [start:event_sourcing_01]
    from event_sourcery.event_sourcing import Aggregate, Repository
    from event_sourcery.event_store import Event

    class SwitchedOn(Event):
        pass

    class LightSwitch(Aggregate):
        category = "light_switch"  # 1

        def __init__(self) -> None:  # 2
            self._switched_on = False

        def __apply__(self, event: Event) -> None:  # 3
            match event:
                case SwitchedOn():
                    self._switched_on = True
                case _:
                    raise NotImplementedError(f"Unexpected event {type(event)}")

        def switch_on(self) -> None:
            if self._switched_on:
                return  # no op
            self._emit(SwitchedOn())

    # --8<-- [end:event_sourcing_01]

    # --8<-- [start:event_sourcing_02_repo]
    repository = Repository[LightSwitch](backend.event_store)
    # --8<-- [end:event_sourcing_02_repo]

    # --8<-- [start:event_sourcing_03]
    from event_sourcery.event_store import StreamUUID

    stream_id = StreamUUID(name="light_switch/1")
    with repository.aggregate(stream_id, LightSwitch()) as light_switch:
        light_switch.switch_on()
        light_switch.switch_on()
    # --8<-- [end:event_sourcing_03]

    events = backend.event_store.load_stream(
        StreamId(name="light_switch/1", category=LightSwitch.category)
    )

    assert len(events) == 1


def test_multitenancy(sqlite_in_memory_backend, event_cls) -> None:
    event_store = sqlite_in_memory_backend.event_store
    InvoicePaid = event_cls

    # --8<-- [start:multitenancy_01]
    scoped_event_store = event_store.scoped_for_tenant("tenant123")
    # --8<-- [end:multitenancy_01]
    stream_id = StreamId(name="invoices/1111")
    event_store.append(InvoicePaid(invoice_number="1111"), stream_id=stream_id)
    subscription = (
        sqlite_in_memory_backend.subscriber.start_from(0)
        .to_events([InvoicePaid])
        .build_iter(timelimit=1)
    )

    # --8<-- [start:multitenancy_02]
    from event_sourcery.event_store import DEFAULT_TENANT
    # --8<-- [end:multitenancy_02]

    # --8<-- [start:multitenancy_03]
    for recorded_event in subscription:
        if recorded_event is None:
            break
        elif recorded_event.tenant_id == DEFAULT_TENANT:
            print(f"Got tenant-less event! {recorded_event}")
        else:
            ...
    # --8<-- [end:multitenancy_03]

    class ExampleAggregate(Aggregate):
        pass

    # --8<-- [start:multitenancy_04]
    scoped_event_store = event_store.scoped_for_tenant("tenant123")

    repository = Repository[ExampleAggregate](scoped_event_store)
    # --8<-- [end:multitenancy_04]

    assert repository is not None


def test_snapshots(sqlite_in_memory_backend) -> None:
    event_store = sqlite_in_memory_backend.event_store

    from event_sourcery.event_store import Event

    # --8<-- [start:snapshots_01]
    class TemperatureChanged(Event):
        reading_in_celsius: int

    stream_id = StreamId(name="temperature_sensor/1")
    events = [TemperatureChanged(reading_in_celsius=reading) for reading in range(100)]
    event_store.append(*events, stream_id=stream_id)

    loaded_events = event_store.load_stream(stream_id)
    print(len(loaded_events))  # 100
    # --8<-- [end:snapshots_01]

    assert len(loaded_events) == 100

    # --8<-- [start:snapshots_02]
    class TemperatureSensorSnapshot(Event):
        readings_so_far: int
        last_reading_in_celsius: int

    # --8<-- [end:snapshots_02]

    # --8<-- [start:snapshots_03]
    last_version = loaded_events[-1].version
    last_event = loaded_events[-1].event

    snapshot = TemperatureSensorSnapshot(
        readings_so_far=100, last_reading_in_celsius=last_event.reading_in_celsius
    )
    wrapped_snapshot = WrappedEvent.wrap(snapshot, last_version)

    event_store.save_snapshot(stream_id, wrapped_snapshot)
    # --8<-- [end:snapshots_03]

    # --8<-- [start:snapshots_04]
    loaded_events = event_store.load_stream(stream_id)
    print(len(loaded_events))  # 1
    assert isinstance(loaded_events[-1].event, TemperatureSensorSnapshot)
    # --8<-- [end:snapshots_04]

    assert len(loaded_events) == 1


def test_versioning(sqlite_in_memory_backend, event_cls) -> None:
    event_store = sqlite_in_memory_backend.event_store
    InvoicePaid = event_cls

    # --8<-- [start:versioning_01]
    stream_id = StreamId(name="invoices/1111")
    an_event = InvoicePaid(invoice_number="1111")
    event_store.append(
        an_event, stream_id=stream_id
    )  # no `expected_version` argument given
    # --8<-- [end:versioning_01]

    # --8<-- [start:versioning_02]
    another_event = InvoicePaid(invoice_number="1112")
    # 👇 this would raise an exception
    # event_store.append(another_event, stream_id=stream_id)
    # --8<-- [end:versioning_02]

    # --8<-- [start:versioning_03]
    present_events = event_store.load_stream(stream_id)
    last_version = present_events[-1].version

    # ... some logic

    another_event = InvoicePaid(invoice_number="1112")
    event_store.append(
        another_event, stream_id=stream_id, expected_version=last_version
    )
    # --8<-- [end:versioning_03]

    # --8<-- [start:versioning_01]
    from event_sourcery.event_store import NO_VERSIONING

    # --8<-- [start:versioning_04]
    stream_id = StreamId(name="invoices/123")

    an_event = InvoicePaid(invoice_number="1111")
    event_store.append(an_event, stream_id=stream_id, expected_version=NO_VERSIONING)

    another_event = InvoicePaid(invoice_number="1112")
    event_store.append(
        another_event, stream_id=stream_id, expected_version=NO_VERSIONING
    )
    # --8<-- [end:versioning_04]


if __name__ == "__main__":
    pytest.main()
