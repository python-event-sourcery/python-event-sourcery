from uuid import uuid4

import pytest

from event_sourcery import StreamId
from event_sourcery.event import Event, WrappedEvent
from event_sourcery.read_model import AsyncCursorsDao, AsyncProjector
from tests.adapter import BackendFacade

from .conftest import (
    AccountCreated,
    AllEventsAsyncReadModel,
    CashDeposited,
    CashWithdrawn,
)


def _projector(
    backend: BackendFacade,
    cursors_dao: AsyncCursorsDao,
    name: str,
    read_model: AllEventsAsyncReadModel,
) -> AsyncProjector:
    return AsyncProjector(
        event_store=backend._async.event_store,
        name=name,
        cursors_dao=cursors_dao,
        read_model=read_model,
    )


def test_projects_the_events(
    async_backend: BackendFacade,
    async_cursors_dao: AsyncCursorsDao,
) -> None:
    read_model = AllEventsAsyncReadModel()
    projector = _projector(
        async_backend, async_cursors_dao, "project_events", read_model
    )
    stream_id = StreamId(uuid4())
    events = [
        AccountCreated(
            national_id="#123", first_last_names="John Doe", initial_deposit=100
        ),
        CashDeposited(amount=200),
        CashWithdrawn(amount=66),
    ]

    async def run() -> None:
        await async_backend._async.event_store.append(*events, stream_id=stream_id)
        wrapped_events = await async_backend._async.event_store.load_stream(
            stream_id=stream_id
        )
        for wrapped_event in wrapped_events:
            await projector.project(wrapped_event, stream_id=stream_id)

    async_backend.runner.run(run())
    assert read_model.get_all() == [
        {
            "stream_id": stream_id,
            "id": "#123",
            "names": "John Doe",
            "balance": 100 + 200 - 66,
        }
    ]


def test_is_able_to_load_up_events_from_untracked_stream(
    async_backend: BackendFacade,
    async_cursors_dao: AsyncCursorsDao,
) -> None:
    read_model = AllEventsAsyncReadModel()
    projector = _projector(
        async_backend, async_cursors_dao, "untracked_stream", read_model
    )
    stream_id = StreamId(uuid4())
    events = [
        AccountCreated(
            national_id="#321", first_last_names="Janine Doe", initial_deposit=200
        ),
        CashDeposited(amount=300),
        CashWithdrawn(amount=100),
    ]

    async def run() -> None:
        await async_backend._async.event_store.append(*events, stream_id=stream_id)
        wrapped_events = await async_backend._async.event_store.load_stream(
            stream_id=stream_id
        )
        await projector.project(wrapped_events[-1], stream_id=stream_id)

    async_backend.runner.run(run())
    assert read_model.get_all() == [
        {
            "stream_id": stream_id,
            "id": "#321",
            "names": "Janine Doe",
            "balance": 400,
        }
    ]


def test_is_able_to_load_up_events_from_tracked_stream(
    async_backend: BackendFacade,
    async_cursors_dao: AsyncCursorsDao,
) -> None:
    read_model = AllEventsAsyncReadModel()
    projector = _projector(
        async_backend, async_cursors_dao, "tracked_stream", read_model
    )
    stream_id = StreamId(uuid4())
    events = [
        AccountCreated(
            national_id="#777", first_last_names="John Wick", initial_deposit=10
        ),
        CashDeposited(amount=7),
        CashWithdrawn(amount=16),
    ]

    async def run() -> None:
        await async_backend._async.event_store.append(*events, stream_id=stream_id)
        wrapped_events = await async_backend._async.event_store.load_stream(
            stream_id=stream_id
        )
        await projector.project(wrapped_events[0], stream_id=stream_id)
        await projector.project(wrapped_events[-1], stream_id=stream_id)

    async_backend.runner.run(run())
    assert read_model.get_all() == [
        {
            "stream_id": stream_id,
            "id": "#777",
            "names": "John Wick",
            "balance": 1,
        }
    ]


def test_ignores_duplicated_events_from_the_middle(
    async_backend: BackendFacade,
    async_cursors_dao: AsyncCursorsDao,
) -> None:
    read_model = AllEventsAsyncReadModel()
    projector = _projector(
        async_backend, async_cursors_dao, "middle_duplicates", read_model
    )
    stream_id = StreamId(uuid4())
    events = [
        AccountCreated(
            national_id="#111", first_last_names="Dwayne", initial_deposit=10
        ),
        CashDeposited(amount=10),
        CashWithdrawn(amount=5),
    ]

    async def run() -> None:
        await async_backend._async.event_store.append(*events, stream_id=stream_id)
        wrapped_events = await async_backend._async.event_store.load_stream(
            stream_id=stream_id
        )
        for wrapped_event in wrapped_events:
            await projector.project(wrapped_event, stream_id=stream_id)
        for wrapped_event in wrapped_events[1:]:
            await projector.project(wrapped_event, stream_id=stream_id)

    async_backend.runner.run(run())
    assert read_model.get_all() == [
        {
            "stream_id": stream_id,
            "id": "#111",
            "names": "Dwayne",
            "balance": 15,
        }
    ]


def test_ignores_duplicated_events_from_the_beginning(
    async_backend: BackendFacade,
    async_cursors_dao: AsyncCursorsDao,
) -> None:
    read_model = AllEventsAsyncReadModel()
    projector = _projector(
        async_backend, async_cursors_dao, "beginning_duplicates", read_model
    )
    stream_id = StreamId(uuid4())
    events = [
        AccountCreated(national_id="#333", first_last_names="Mark", initial_deposit=5),
        CashDeposited(amount=5),
        CashWithdrawn(amount=10),
    ]

    async def run() -> None:
        await async_backend._async.event_store.append(*events, stream_id=stream_id)
        wrapped_events = await async_backend._async.event_store.load_stream(
            stream_id=stream_id
        )
        for _ in range(2):
            for wrapped_event in wrapped_events:
                await projector.project(wrapped_event, stream_id=stream_id)

    async_backend.runner.run(run())
    assert read_model.get_all() == [
        {
            "stream_id": stream_id,
            "id": "#333",
            "names": "Mark",
            "balance": 0,
        }
    ]


def test_raises_exception_when_trying_to_project_unversioned_event(
    async_backend: BackendFacade,
    async_cursors_dao: AsyncCursorsDao,
) -> None:
    read_model = AllEventsAsyncReadModel()
    projector = _projector(
        async_backend, async_cursors_dao, "unversioned_event", read_model
    )
    unversioned_event = WrappedEvent[Event](
        event=AccountCreated(
            national_id="#333", first_last_names="Mark", initial_deposit=5
        ),
        version=None,
    )

    async def run() -> None:
        with pytest.raises(projector.CantProjectUnversionedEvent):
            await projector.project(unversioned_event, stream_id=StreamId(uuid4()))

    async_backend.runner.run(run())
