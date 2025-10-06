# Dependencies and distribution

Date: 2024-07-26

## Status

Accepted

## Context

Event Sourcery supports multiple backends, such as SQLAlchemy, EventStoreDB. More adapters will appear in the future.

Each integration has its own dependencies, for example EventStoreDB relies on `esdbclient` which in turn depends on `grpcio`.

When someone wants to use the library for e.g. Django or SQLAlchemy, they don't need aforementioned packages.

The approach to packaging and releases should make it possible for library clients to install only packages that are required in their setup.

## Considered approaches

### Single package with extras

In this approach, we release a single python_event_sourcery package that includes all modules i.e. "core" + adapters for esdb, django and sqlalchemy (+ possibly more in the future).

To control optional dependencies, we'll use optional dependencies + "extras" feature which is widely supported in popular Python packaging tools.

We already have it implemented for Django - when someone installs our library using "pip install python-event-sourcery[django]", we'll also install Django framework.

**NOTE** Real-world Django projects would already have Django installed FIRST and they'll be adding our library LATER. However, it still makes sense to have Django as an optional dependency and extra to cross-validate the supported version. If someone has Django installed and its version frozen, but it's not compatible with our library, they'll see an error.

Extras propositions for the current project structure:
- `sqlalchemy` - SQLAlchemy adapter
- `esdb` - EventStoreDB adapter

For example, when someone wants to use our library with SQLAlchemy, they'll have to install it using `pip install python-event-sourcery[sqlalchemy]`.

Downside: maintainers of the library are aware of some in-house solutions that doesn't support "extras". We acknowledge the existence of such a niche, but we won't be treating is a blocker.

### Multiple packages

In this approach, python-event-sourcery would be split into multiple **separately installable** packages, i.e.:

- `python_event_sourcery_core` - core functionality
- `python_event_sourcery_sqlalchemy` - SQLAlchemy adapter, depending on `python_event_sourcery_core`
- `python_event_sourcery_esdb` - EventStoreDB adapter, depending on `python_event_sourcery_core`
- `python_event_sourcery_django` - Django adapter, depending on `python_event_sourcery_core`

We could still have them all in a single repository and maintain a single test suite, but build & release process would be uploading separate packages to PyPI.

This would require a work to create multiple pyproject.toml files, one per each package and put there the dependency on the core package.

Downside: in the current setup we have only support for different backends. In the future, when e.g. support for Kafka or RabbitMQ will be added, installation would become more cumbersome. For example, if someone would be using SQLAlchemy and Kafka, they would have to install two packages. With extras, it'll still be a single package but with to extras.  

## Decision

We decided to go with the "Single package with extras" approach.

## Consequences

As a consequence, we'll have to put work into maintaining the extras feature in the pyproject.toml file.
