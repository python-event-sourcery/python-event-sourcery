# Packaging of the event_store package

Date: 2025-10-04

## Status

Accepted

## Context

We want to keep the project structure clear and intuitive. Import paths should reflect the functionality provided by each package, regardless from the code evolution. That's why implementation of our core event_store package will be kept in `_internal` subpackage (keeping it as protected package).
In root `event_store` package we will keep public API structure with proxy imports to implementation in `_internal`.
Proxy imports will be organized in modules reflecting functionality (e.g.`encryption`, `event`, `types` etc.).

## Decision

Implementation of the `event_store` will be moved into `_internal` subpackage. Root of `event_store` package will keep public API structure with proxy imports to implementation in `_internal`.
