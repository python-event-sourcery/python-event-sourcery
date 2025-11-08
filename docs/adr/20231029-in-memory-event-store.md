# InMemory Event Store

Date: 2023-10-29

## Status

Accepted

## Context

Features of core event store requires integration tests with every backend implementation.
In this context first tests were prepared.

## Decision

InMemory event store strategy will be used as default for feature tests. Also, it's a 
good starting point to experiment with library or start a project postponing
infrastructure decisions.

## Consequences

Possible lack of testing backend-specific consequences for features.
This will require additional backend-specific tests.
