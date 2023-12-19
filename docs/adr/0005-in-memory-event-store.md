# 5. InMemory Event Store

Date: 2023-10-29

## Status

Accepted

## Context

Features of core event store requires integration tests with every backend implementation.
In this context first tests were prepared.

We plan to prepare additional features (application building blocks) on top of event store.
There is no need to test backend agnostic features with every backend. 

## Decision

InMemory event store strategy will be used as default for feature tests.

## Consequences

Possible lack of testing backend-specific consequences for features.
This will require additional backend-specific tests.
