from typing import NoReturn, Callable

from kombu import Connection, Exchange, Queue, Message
from kombu.connection import ConnectionPool
from kombu.pools import connections
from pydantic import AmqpDsn, BaseSettings, Field

__all__ = ["publish_event", "declare_exchange"]

from event_sourcery import Metadata, Subscription, Event
from event_sourcery.event_registry import event_name


class BrokerSettings(BaseSettings):
    BROKER_URL: AmqpDsn = Field(default="amqp://guest:guest@rabbitmq//")


class PoolFactory:
    _pool: ConnectionPool | None = None
    _config: BrokerSettings | None = None

    @classmethod
    def configure(cls, broker_url: str) -> None:
        if cls._pool is not None:
            cls._pool.force_close_all()
            cls._pool = None

        cls._config = BrokerSettings(BROKER_URL=broker_url)

    @classmethod
    def get(cls) -> ConnectionPool:
        if cls._config is None:
            cls._config = BrokerSettings()

        if cls._pool is None:
            connection = Connection(
                cls._config.BROKER_URL, transport_options={"confirm_publish": True}
            )
            cls._pool = connections[connection]
        return cls._pool


EVENT_SOURCERY_EXCHANGE = "event_sourcery.events"


def publish_event(metadata: Metadata, stream_name: str | None) -> None:
    name = event_name(type(metadata.event))
    _publish(
        routing_key=name,
        headers={
            "event": name,
            "stream_name": stream_name,
            "stream_category": stream_name.split(".")[0] if stream_name else None,
        },
        message=metadata.json(),
        exchange=EVENT_SOURCERY_EXCHANGE,
    )


def declare_exchange() -> None:
    _declare(Exchange(name=EVENT_SOURCERY_EXCHANGE, type="headers"))


def _publish(
    routing_key: str, message: str, exchange: str, headers: dict,
) -> None:
    with PoolFactory.get().acquire(block=True) as conn:
        producer = conn.Producer()
        producer.publish(
            message,
            exchange=exchange,
            routing_key=routing_key,
            headers=headers,
            content_type='application/json',
        )


def _declare(queue_or_exchange: Exchange | Queue) -> None:
    with PoolFactory.get().acquire(block=True) as conn:
        queue_or_exchange(conn).declare()


def consume(subscription: Subscription, listener: Callable[[Metadata], None]) -> NoReturn:
    queue = Queue(f"event_sourcery.{listener.__name__}", durable=True)
    _declare(queue)

    def callback(body: dict, message: Message) -> None:
        event_name = message.headers["event"]
        event_type = Event.__registry__.type_for_name(event_name)

        metadata = Metadata[event_type](**body)

        try:
            listener(metadata)
        except Exception:
            message.reject()
            raise
        else:
            message.ack()

    with PoolFactory.get().acquire(block=True) as conn:
        for event_type in subscription.event_types:
            queue(conn).bind_to(exchange=EVENT_SOURCERY_EXCHANGE, arguments={
                "event": event_name(event_type),
            })

        for stream_category in subscription.stream_categories:
            queue(conn).bind_to(exchange=EVENT_SOURCERY_EXCHANGE, arguments={
                "stream_category": stream_category,
            })

        with conn.Consumer([queue], callbacks=[callback]):
            while True:
                try:
                    conn.drain_events()
                except KeyboardInterrupt:
                    return

