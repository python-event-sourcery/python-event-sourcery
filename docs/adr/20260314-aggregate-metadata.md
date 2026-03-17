# Aggregate Metadata

Date: 2026-03-14

## Status

Accepted

## Context

Currently `Repository.aggregate()` yields only the aggregate instance. The caller has no access to stream-level information such as:

- What is the current version of the aggregate?
- Is this a new aggregate (no prior events in the stream)?
- When was the stream created or last modified?
- What stream identity was used?

This information is essential for many use cases:
- Detecting whether an aggregate is being created for the first time (e.g. to enforce idempotent creation)
- Knowing the version for external optimistic concurrency checks or ETags
- Accessing timestamps for auditing or display purposes

Other event sourcing frameworks consistently expose this kind of metadata:
- **Marten** returns `StreamState` with `Version`, `Created`, `LastTimestamp`, `AggregateType` via `FetchForWriting<T>`
- **Eventide** returns `(entity, version)` tuple, with `:no_stream` sentinel for non-existent streams
- **Axon** exposes `@AggregateVersion` and `AggregateLifecycle.isLive()`
- **Ecotone** enriches events with `_aggregate_version`, `_aggregate_type` headers

## Decisions

### D1: Wrapper pattern — `WrappedAggregate`

Following the established pattern of `WrappedEvent` which wraps `Event` with metadata, the repository will return a `WrappedAggregate` that wraps the aggregate instance with stream metadata. The aggregate itself remains a pure domain object with no knowledge of infrastructure concerns.

```python
with repo.aggregate(uuid, LightSwitch()) as wrapped:
    if wrapped.is_new:
        wrapped.aggregate.turn_on()
```

**Rationale:** This is consistent with `WrappedEvent[TEvent]` which carries `event`, `version`, `uuid`, `created_at`, and `context` alongside the event itself. `WrappedAggregate[TAggregate]` follows the same convention — the wrapper holds metadata, the inner object stays pure.

**Migration:** This is a breaking change. Existing callers using `as aggregate` will need to change to `as wrapped` and access `wrapped.aggregate`. Given the library is pre-1.0, this is acceptable.

### D2: Fields on `WrappedAggregate`

| Field | Type | Source |
|---|---|---|
| `aggregate` | `TAggregate` | The aggregate instance |
| `version` | `int` (computed) | Stored version + count of pending changes in aggregate |
| `is_new` | `bool` (computed) | `True` when stored version is 0 (no events existed before load) |
| `stream_id` | `StreamId` | Built from UUID + aggregate category |
| `created_at` | `datetime \| None` | Timestamp of the first event in the stream |
| `updated_at` | `datetime \| None` | Timestamp of the last event in the stream |
| `context` | `Context \| None` | The context passed to the repository for this operation |

**`version` is computed dynamically.** It reflects the stored version plus any uncommitted changes the aggregate has emitted. This means:
- After loading an aggregate with 5 events: `version == 5`
- After emitting 2 more events: `version == 7`
- After persisting (context exit): version reflects the final stored state

This is achieved by reading the aggregate's `__changes__` property and computing `stored_version + len(aggregate.__changes__)` on access.

**`is_new` is based on stored version only**, not including pending changes. An aggregate that was just created and has emitted its first event is still `is_new == True` — it didn't exist before this session. This matches Eventide's `:no_stream` semantics.

### D3: Class naming and location

The class will be called `WrappedAggregate`. It is a generic dataclass `WrappedAggregate[TAggregate]`, mirroring `WrappedEvent[TEvent]`. It lives in the `event_sourcery.event_sourcing` module alongside `Aggregate` and `Repository`.

**Rationale:** `WrappedAggregate` directly mirrors `WrappedEvent` — both are generic wrappers that pair a domain object with infrastructure metadata. The naming convention is already established in the project. A dataclass is used instead of a Pydantic model because `WrappedAggregate` is a simple data holder — it does not need serialization, validation, or schema generation. A dataclass keeps the dependency footprint minimal and the implementation straightforward.

## Solution Proposal

### New class: `WrappedAggregate`

```python
# event_sourcery/event_sourcing/aggregate.py

TAggregate = TypeVar("TAggregate", bound=Aggregate)

@dataclass
class WrappedAggregate(Generic[TAggregate]):
    aggregate: TAggregate
    stream_id: StreamId
    context: Context | None
    created_at: datetime | None
    updated_at: datetime | None
    stored_version: int

    @property
    def version(self) -> int:
        return self.stored_version + len(
            getattr(self.aggregate, "__changes__", [])
        )

    @property
    def is_new(self) -> bool:
        return self.stored_version == 0

```

### Changes to `Repository`

```python
# event_sourcery/event_sourcing/repository.py

@contextmanager
def aggregate(
    self,
    uuid: StreamUUID,
    aggregate: TAggregate,
    context: Context | None = None,
) -> Iterator[WrappedAggregate[TAggregate]]:
    stream_id = StreamId(uuid=uuid, name=uuid.name, category=aggregate.category)
    stored_version, created_at, updated_at = self._load(stream_id, aggregate)
    wrapped = WrappedAggregate(
        aggregate=aggregate,
        stream_id=stream_id,
        context=context,
        created_at=created_at,
        updated_at=updated_at,
        stored_version=stored_version,
    )
    yield wrapped
    self._save(aggregate, stored_version, stream_id, context)
```

The `_load` method will be updated to extract `created_at` from the first event's timestamp and `updated_at` from the last event's timestamp during replay.

### Public API exports

`WrappedAggregate` will be exported from `event_sourcery.event_sourcing` package `__init__.py`.

## Consequences

- **Breaking change** in `Repository.aggregate()` yield type — all callers must update from `as aggregate` to `as wrapped` and access `wrapped.aggregate`.
- Consistent with the existing `WrappedEvent` pattern — both domain objects (`Event`, `Aggregate`) are wrapped with metadata by infrastructure, never polluted directly.
- The aggregate remains a pure domain object — no infrastructure leakage.
- `version` property provides a live view of the aggregate's version including pending changes, useful for logging/debugging.
- `is_new` enables idempotent aggregate creation patterns without checking version manually.
- `created_at` / `updated_at` are derived from event timestamps — no additional storage or queries needed.
- `context` reference enables callers to inspect or pass along the context used for the current operation.
- `version` reads `aggregate.__changes__` dynamically, so it updates automatically as events are emitted.
