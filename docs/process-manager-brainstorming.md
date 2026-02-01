# Process Manager Brainstorming (WIP)

This note captures the current brainstorming about a Process Manager for Event
Sourcery. It is not a finalized design.

## Core idea
- State machines (states + transitions) live in the library.
- A state transition is recorded as an event and becomes a task.
- Tasks can be executed synchronously (inline) or asynchronously (by a worker pool).
- All process history lives in one stream (single source of truth).

## Deterministic orchestration + side effects
- The Process Manager is deterministic: given state + event, it decides which
  transitions to plan.
- Side effects are performed outside the Process Manager (task execution).
- Task results come back as events in the same stream.

## Single-stream consistency
- One process instance = one event stream.
- All intent and outcomes are captured in that stream:
  - Transition planned
  - Task completed / failed
  - Process completed / failed
- Replay should be fully deterministic from the stream alone.

## Events to represent transitions and tasks (sketch)
```
TransitionPlanned:
  - process_id
  - machine_id (e.g., instance id)
  - transition name
  - from_state / to_state
  - task_type
  - task_mode: "sync" | "async"
  - task_id

TaskCompleted:
  - process_id
  - machine_id
  - task_id
  - transition name

TaskFailed:
  - process_id
  - machine_id
  - task_id
  - transition name
  - reason
```

## Example scenario: rebase failed -> close three instances
Context: ProcessManager receives `RebaseFailed(rebase_id, [A,B,C])` and must move
three instances from Working to Closed via async tasks.

Proposed event sequence in the single process stream:
1. RebaseFailed(rebase_id, [A,B,C])
2. TransitionPlanned(machine_id=A, from=Working, to=Closing, task=CloseInstance)
3. TransitionPlanned(machine_id=B, from=Working, to=Closing, task=CloseInstance)
4. TransitionPlanned(machine_id=C, from=Working, to=Closing, task=CloseInstance)
5. TaskCompleted(machine_id=A, task_id=...)
6. TaskCompleted(machine_id=B, task_id=...)
7. TaskCompleted(machine_id=C, task_id=...)
8. ProcessCompleted(rebase_id)

Notes:
- TransitionPlanned both records the state transition and triggers the task.
- Workers subscribe to TransitionPlanned and emit TaskCompleted/TaskFailed back
  to the same stream.

## Multiple state machines per process
- A single process can manage multiple machines (e.g., per-instance sub-state).
- State can be represented as a map: machine_id -> state.

## Idempotency and concurrency (notes)
- Use task_id from TransitionPlanned for idempotent task execution.
- Use optimistic concurrency (expected version) when appending to stream.
- A simple inbox (event UUIDs) can protect against duplicate event handling.

## Open questions
- Should TransitionPlanned also be the only representation of state change,
  or do we need explicit StateChanged events?
- How to model retries and timeouts for failed tasks?
- How much of this is core vs optional adapter (FSM DSL)?
