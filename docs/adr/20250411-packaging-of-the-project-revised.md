# Packaging of the project

Date: 2025-04-11

## Status

Accepted

## Context

In [ADR 20231027 #1](20231027_1-packaging-of-the-project.md) the decision was made to package the project in the following way:

- `aggregate`
- `event_store`
- `read_model`
 
During documentation writing it became obvious that `aggregate` name is not accurate because inside this package there are more things than just `Aggregate` class.

## Decision

`aggregate` will be renamed to `event_sourcing` to more accurately reflect its contents.
