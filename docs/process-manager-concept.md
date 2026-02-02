# Process Manager Concept for Event Sourcery

This document captures a **concept proposal** for adding a Process Manager
to `event_sourcery`. It describes **how the concept fits the current library**,
**what needs to be implemented**, and **where new files should live**.

The goal is to support a **single process stream (event history)** as the source
of truth, while **transition execution happens asynchronously** via task/workflow
streams or external workers.

---

## 1) Concept Summary

**Core idea**
- Each process instance has **one process stream** that records the state machine
  history (deterministic, replayable).
- The Process Manager is **deterministic**: it decides transitions based only on
  current state + incoming event.
- Transition execution happens **outside** the Process Manager via **tasks**.
- Task execution may be multi-step and stored in **separate task/workflow streams**.
- Task outcomes are written back into the **process stream** as events.
- The process can be **cancelled/interrupted**, with late task results ignored or
  explicitly cancelled.

---

## 2) How this maps to current `event_sourcery`

**Already available**
- `EventStore` and `StreamId` support append‑only streams.
- `Event` + `WrappedEvent` provide typed event payloads.
- `Repository` + `Aggregate` show how to replay state from a stream.
- `SubscriptionBuilder` provides stream/event subscriptions.
- `Outbox` can deliver commands/tasks to an external bus.

**What’s missing**
There is no Process Manager module, no event→process routing, no global
subscription cursor, and no task/workflow model. These should be added.

---

## 3) Proposed module structure (files to add)

```
event_sourcery/
  process_manager/
    __init__.py
    engine.py          # ProcessEngine: handles incoming events
    state.py           # ProcessState (event-sourced)
    decision.py        # Decision(events, commands)
    manager.py         # ProcessManager protocol
    locator.py         # ProcessLocator (event -> process_id)
    context.py         # ProcessContext (ergonomic helpers)
    events.py          # Optional: shared PM events (TransitionPlanned, etc.)
    tasks.py           # Optional: task command models

docs/
  process-manager-concept.md            # this document
  process-manager-pseudocode-proposal.md
  process-manager-brainstorming.md
```

---

## 4) Core Components (concept)

### a) ProcessState (event‑sourced)
- Replayed from the **process stream**.
- Holds deterministic state only (no external IO).

### b) ProcessManager (decision logic)
- Pure function: `decide(state, event) -> Decision`
- Must be deterministic and replayable.

### c) Decision
- A simple container: `{events: [Event], commands: [Command]}`
- `events` are appended to the **process stream**
- `commands` are published to tasks/workers (or task streams)

### d) ProcessEngine
Orchestrates flow:
1. Receives external event
2. Uses `ProcessLocator` to find `process_id`
3. Loads `ProcessState` from stream
4. Calls `ProcessManager.decide`
5. Appends resulting events to process stream
6. Publishes tasks/commands

### e) ProcessLocator (event → process_id)
Defines how events are correlated to a process instance.
E.g. look at event payload or correlation_id in `Context`.

### f) Task/Workflow execution (outside PM)
Tasks can be implemented as:
- **Task streams** (`task::<id>` category)
- or **external worker queue** via Outbox

The Process Manager only cares about **final task outcomes**, which are written
back to the **process stream**.

---

## 5) Proposed event model (process stream)

Minimal set of event types:

```
ProcessStarted
TransitionPlanned(transition_id, from_state, to_state, task_id, task_stream_id)
TaskCompleted(task_id, transition_id, result)
TaskFailed(task_id, transition_id, reason)
ProcessCancelled(reason)
ProcessCompleted
```

These are normal `Event` subclasses.

---

## 6) Missing pieces to implement

### 1) Process Manager API
