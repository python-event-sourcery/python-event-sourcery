# Process Manager Pseudocode Proposal (Single Process Stream + Async Tasks)

This proposal captures a **Python-style pseudocode** for a Process Manager
implementation where:

- The **process stream** is the single source of truth for state and decisions.
- **Execution is asynchronous** and happens in separate task/workflow streams.
- The process can be **cancelled/interrupted** at any time.

The code below is intentionally simplified to support discussion of usability
and API ergonomics.

---

## 1) Events (Process Stream)

```python
class Event: ...

@dataclass(frozen=True)
class ProcessStarted(Event):
    process_id: UUID

@dataclass(frozen=True)
class TransitionPlanned(Event):
    process_id: UUID
    transition_id: UUID
    from_state: str
    to_state: str
    task_type: str
    task_id: UUID
    task_stream_id: UUID

@dataclass(frozen=True)
class TaskCompleted(Event):
    process_id: UUID
    transition_id: UUID
    task_id: UUID
    result: dict

@dataclass(frozen=True)
class TaskFailed(Event):
    process_id: UUID
    transition_id: UUID
    task_id: UUID
    reason: str

@dataclass(frozen=True)
class ProcessCancelled(Event):
    process_id: UUID
    reason: str

@dataclass(frozen=True)
class ProcessCompleted(Event):
    process_id: UUID
```

---

## 2) Commands (Outgoing)

```python
class Command: ...

@dataclass(frozen=True)
class StartTask(Command):
    task_id: UUID
    task_stream_id: UUID
    task_type: str
    payload: dict

@dataclass(frozen=True)
class CancelTask(Command):
    task_id: UUID
```

---

## 3) State

```python
@dataclass
class ProcessState:
    status: str = "New"  # New | Running | Cancelled | Completed
    machine_state: Dict[str, str] = field(default_factory=dict)
    active_tasks: Dict[UUID, UUID] = field(default_factory=dict)  # task_id -> transition_id

    def is_cancelled(self) -> bool:
        return self.status == "Cancelled"
```

---

## 4) Decision Model

```python
@dataclass
class Decision:
    events: List[Event]
    commands: List[Command]
```

---

## 5) Process Manager Interface

```python
class ProcessManager(Protocol):
    def decide(self, state: ProcessState, event: Event) -> Decision:
        ...
```

---

## 6) Example Process Manager (Sketch)

```python
class RebaseFailureProcess(ProcessManager):
    def decide(self, state: ProcessState, event: Event) -> Decision:
        if isinstance(event, ProcessCancelled):
            # Hard cancel: stop planning, optionally cancel active tasks
            cmds = [CancelTask(task_id=t) for t in state.active_tasks.keys()]
            return Decision(events=[], commands=cmds)

        if state.is_cancelled():
            # Ignore late results
            return Decision(events=[], commands=[])

        if isinstance(event, TaskCompleted):
            if self._all_done(state):
                return Decision(events=[ProcessCompleted(event.process_id)], commands=[])
            return Decision(events=[], commands=[])

        if isinstance(event, TaskFailed):
            return Decision(events=[ProcessCancelled(event.process_id, "task failed")], commands=[])

        if isinstance(event, RebaseFailed):  # domain event
            events, cmds = [], []
            for machine_id in event.instance_ids:
                transition_id = new_uuid()
                task_id = new_uuid()
                task_stream_id = new_uuid()

                events.append(
                    TransitionPlanned(
                        process_id=event.rebase_id,
                        transition_id=transition_id,
                        from_state="Working",
                        to_state="Closing",
                        task_type="CloseInstance",
                        task_id=task_id,
                        task_stream_id=task_stream_id,
                    )
                )
                cmds.append(
                    StartTask(
                        task_id=task_id,
                        task_stream_id=task_stream_id,
                        task_type="CloseInstance",
                        payload={"instance_id": machine_id},
                    )
                )

            return Decision(events=events, commands=cmds)

        return Decision(events=[], commands=[])
```

---

## 7) Process Engine (Event Loop)

```python
class ProcessEngine:
    def __init__(self, store, outbox, manager: ProcessManager):
        self.store = store
        self.outbox = outbox
        self.manager = manager

    def on_event(self, process_id: UUID, event: Event) -> None:
        state = self.store.load_state(process_id)
        decision = self.manager.decide(state, event)
        self.store.append(process_id, decision.events, expected_version=state.version)
        self.outbox.publish(decision.commands)
```

---

## 8) Task Worker (Execution Side)

```python
class TaskWorker:
    def on_command(self, cmd: StartTask) -> None:
        # run multi-step workflow in a separate task stream
        result = run_workflow(cmd.task_stream_id, cmd.task_type, cmd.payload)
        if result.ok:
            publish_process_event(TaskCompleted(...))
        else:
            publish_process_event(TaskFailed(...))
```

---

## Notes on Usability

- The minimal contract is: **`decide(state, event) -> Decision`**.
- Deterministic replay is guaranteed by keeping **all state transitions** in the
  process stream.
- Task/workflow detail lives outside the PM, but is linked via `task_id` and
  `transition_id`.
- Cancellation can be modeled as **hard** (ignore late results) or
  **cooperative** (issue `CancelTask` and wait for `TaskCancelled`).

