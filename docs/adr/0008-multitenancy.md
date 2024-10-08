# 8. Multitenancy

Date: 2024-10-07

## Status

Proposed

## Context

One of the missing features for v1.0 is support for multitenancy, i.e. data isolation for separate customers (tenants) inside a single application.

The basic rule is that data from one tenant must not be visible for other tenant.

We also need to make sure library would still operate in tenant-less context. For example, one may define a subscription that builds read model. In such a context, we except all data to be available. Also, some applications may wish to maintain tenant-less, "global" data.

There are multiple approaches to multitenancy:
- row-level multitenancy - each row in a table has a tenant id
- schema-level multitenancy - each tenant has its own schema
- database-level multitenancy - each tenant has its own database.

In the library, we'll natively support row-level multitenancy. Other approaches are also possible to implement even today with the current state of the library. For that purpose, one can create separate objects for `EventStore`, each connecting to other schema or database. Of course this would require e.g. doing schema migration for each tenant schema or database, but if this is a level of isolation required, it means it would have to be necessary anyway and library itself has nothing to do with it. 

Since all events are organized into streams, the problem can be reduced to stream visibility. A stream MAY have a tenant id. For "global" streams, tenant id is empty (effectively, `null` / `None`).

Decisions to make:
- do we allow streams to coexist with the same name and ID in different tenants, as well as tenant-less context?
- what type of column should be used for tenant id?

## Decision

### Streams coexistence with the same name and ID in different tenants

To guarantee full data separation we'll allow streams with the same ID and/or name exist in any tenant, as well as in tenant-less context. For example, if we have 10 tenants, there might be 11 streams with the same ID or name.

This is to avoid awkward API behaviour when trying to load a stream by id when the stream exists but in the current context we have no access to it.

In an ideal world with full data separation, we'd return something like "stream not found" but with globally unique Stream IDs we should deny access, thus give away the fact that stream exists. If we'd returned "stream not found", we would suggest that one can create a stream with the same ID. When they would attempt to do so, we'd have to handle uniqueness violation, still giving away the fact that stream exists in some other context. 

This is a security risk for the library users and may be abused by attacker. We'd rather be on the safe side and make it impossible for users of the library to introduce vulnerabilities into their software.

On the brightside, this makes exposing stream ids in URLs or other places kinda ok. UUIDs are still poor from UX perspective, but at least data separation is still guaranteed.

| Stream tenant | mode        | access attempt by | response |
|---------------|-------------|-------------------|----------|
| null          | tenant-less | by id             | yes      |
| null          | tenant-less | by name           | yes      |
| null          | as tenant1  | by id             | no       |
| null          | as tenant1  | by name           | no       |
| 1             | tenant-less | by id             | no       |
| 1             | tenant-less | by name           | no       |
| 1             | as tenant1  | by id             | yes      |
| 1             | as tenant1  | by name           | yes      |
| 1             | as tenant2  | by id             | no       |
| 1             | as tenant2  | by name           | no       |

### Type of column for tenant id

In the past we were wondering whether we should use integer or UUID type for tenant id. We acknowledged the fact that UUID is actually a superset of integer type in many databases, so we could go with UUID. 

However, this is not the type used in other solutions.

[MartenDB](https://martendb.io/documents/multi-tenancy.html#implementation-details) uses varchar column for tenant_id. If some documents in MartenDB are insterted in a tenant-less context they get default value of `*DEFAULT*`.

In our case we'll stick with `tenantless` value.

Varchar is definitely less performant than integer or UUID, however this shouldn't be a blocker. We'll add an index to the column because it will be used in all queries.

## Consequences

Implementing row-level multitenancy in the library entails adding a column "tenant_id" of type `varchar` to the `streams` table. This column will be indexed.

Since many streams can co-exist with the same ID or name, we have to start passing `tenant_id` to any library code that is responsible handling streams, e.g. in projections. This is quite huge change in the library, yet is required to get complete data separation and allows to build the best API for the users of the library.
