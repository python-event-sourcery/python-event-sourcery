# Process Manager Library: Research and Planning Draft

## Goal
Design a Process Manager library for event-sourced systems that coordinates
long-running business processes. It listens to events, maintains process state,
and issues commands. It supports multiple parallel sub-states, idempotency,
retries, and compensations.

## 1) Research and Inspirations
- Patterns: Saga (orchestrated vs choreographed), Process Manager, long-running
  workflows, compensating transactions, outbox/inbox, idempotent consumer,
  event choreography, command routing.
- Concepts: causal ordering, correlation/causation IDs, process instance
  identity, temporal decoupling, retries with backoff, replay and snapshotting.
- Existing libraries/frameworks: event-sourcing toolkits, workflow engines,
  orchestration frameworks, message buses, and BPM/temporal systems for
  inspiration on state, timeouts, and retries.
- Documentation sources: DDD literature (Evans/Vernon), microservices
  transaction patterns, event-driven architecture references, distributed
  systems consistency models.

### Additional inspirations
- Stories (proofit404/stories): inspiration for a lightweight, step-based DSL
  (sequence of small, composable steps with explicit state). Useful as optional
  sugar around core `handle(state, event) -> commands` API.
- Temporal Workflows: inspiration for strict separation of deterministic
  orchestration from side effects (activities). Reinforces requirement that
  process logic should be replayable and deterministic, while commands are
  executed outside the process manager.
- python-statemachine: inspiration for explicit state graphs, transitions,
  guards, and actions. Suggests an optional FSM adapter or transition-table
  mode for users who want declarative state transitions.

## 2) Initial Requirements
### Functional
- Subscribe to one or more event streams and filter/route by type.
- Maintain state per process instance, including multiple sub-states.
- Emit commands as outputs (to other bounded contexts/services).
- Support timeouts, delays, and scheduled follow-ups.
- Allow compensations and rollbacks based on failure events.
- Provide correlation across events/commands for traceability.

### Non-functional
- Idempotent event handling.
- Deterministic state transitions for replay.
- Concurrency safety for parallel event processing.
- Pluggable storage and transport backends.
- Observability (logging, metrics, tracing).
- Testability (deterministic simulation and in-memory adapters).

## 3) Initial Domain Model
- ProcessManager: orchestrator that handles events and decides next commands.
- ProcessInstance: state container per process identity (e.g., PR id).
- ProcessState: serializable state; supports sub-states (e.g., env instances).
- ProcessEvent: input events the manager reacts to.
- ProcessCommand: output commands to other services/domains.
- ProcessPolicy: rules for transitions and compensations.
- ProcessTimer: scheduled triggers or timeouts.

## 4) Architecture Sketch
- Core module
  - ProcessManager interface: handle(event) -> commands
  - State transition engine: pure function for deterministic updates
  - Idempotency guard and replay logic
- State module
  - Process state storage abstraction (read/write, snapshots)
  - Versioning/concurrency control
- Messaging module
  - Event subscription, filtering, routing
  - Command dispatcher/output port
- Scheduling module
  - Timeouts, retries, delayed events
- Observability module
  - Logs, metrics, trace IDs, audit trail

## 5) MVP Scope
- One ProcessManager type.
- Event in -> state transition -> commands out.
- In-memory storage plus a simple persistence adapter interface.
- Idempotency based on event IDs.
- Simple timeout/retry mechanism.
- Minimal examples and test harness.

## 6) Risks and Hard Problems
- Concurrent event handling and race conditions.
- Exactly-once vs at-least-once delivery semantics.
- Idempotency in the presence of retries and duplicates.
- Replay correctness and backward-compatible state evolution.
- Compensations that are not fully reversible.
- Managing long-lived process state and version upgrades.
