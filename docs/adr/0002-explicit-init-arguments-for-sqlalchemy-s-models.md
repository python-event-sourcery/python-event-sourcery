# 2. Explicit __init__ arguments for SQLAlchemy's models

Date: 2023-09-03

## Status

Draft

## Context

We aim for having full support regarding 

## Possible solutions

### Use native support for dataclasses in SQLAlchemy

Starting from SQLAlchemy 2.0, there's a [native support for dataclasses](https://docs.sqlalchemy.org/en/20/changelog/whatsnew_20.html#native-support-for-dataclasses-mapped-as-orm-models).

However, it's less seamless than one might initially imagine. It comes down to inheriting explicitly from another base class, namely `sqlalchemy.orm.MappedAsDataclass` and using it as a base for models:
```python
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import MappedAsDataclass

class Base(MappedAsDataclass, DeclarativeBase):
    """subclasses will be converted to dataclasses"""

class User(Base):
    __tablename__ = "user_account"

    id: Mapped[intpk] = mapped_column(init=False)
```

As a result, `User` becomes a dataclass with attached SQLAlchemy's behaviour.

In terms of risk, this may cause compatibility issues. As a reminder, Event Sourcery's models are declared as bare classes (notice lack of inheritance from `Base`):

```python
class Stream:
    __tablename__ = "event_sourcery_streams"
    __table_args__ = (
        UniqueConstraint("uuid", "category"),
        UniqueConstraint("name", "category"),
    )

    id = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
```

The assumption is that someone setting up a project with SQLAlchemy will have their own `Base` class and models. The library will let them attach our models to their declarative base later using `event_sourcery_sqlalchemy.models.configure_models`, like:

```python
@as_declarative()
class Base:
    pass


# initialize Event Sourcery models, so they can be handled by SQLAlchemy and e.g. alembic
configure_models(Base)
```

The exception is raised in case `MappedAsDataclass` appears multiple time in model's MRO, for example:
- let's say we have a base class for our models that inherits from `MappedAsDataclass`
- someone has their own `Base` that also inherits from `MappedAsDataclass`

```
sqlalchemy.exc.InvalidRequestError: Class <class 'event_sourcery_sqlalchemy.models.Stream'> is already a dataclass; ensure that base classes / decorator styles of establishing dataclasses are not being mixed. This can happen if a class that inherits from 'MappedAsDataclass', even indirectly, is been mapped with '@registry.mapped_as_dataclass'
```

To reproduce, add `MappedAsDataclass` as a base to any model and use this snippet:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

from event_sourcery_sqlalchemy.models import configure_models


engine = create_engine(
    "sqlite+pysqlite:///:memory:", echo=True, future=True
)


class Base(MappedAsDataclass, DeclarativeBase):
    pass


Base.metadata.create_all(bind=engine)


# initialize Event Sourcery models, so they can be handled by SQLAlchemy and e.g. alembic
configure_models(Base)
```


### Create base class for models with overridden __init__

There is a recipe for providing base class model with overriding `__init__`:
```python
class ModelBase:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        return super().__init__(*args, **kwargs)
```

This basically makes mypy unable to verify anything extra because such a signature allows everything to be passed in. Conversely, all operations are considered to be correct from type checker's perspective.

This solution is a bit tricky and just gets rid of warnings, but doesn't give us any additional benefits.

### Define our own, explicit `__init__` definition

We can simply provide tailored `__init__` for each model to get type safety out of the box.

```python
class Stream:
    def __init__(self) -> None:
        pass


```

This is safe & compatible with other ORM's features because SQLAlchemy uses other means to build an object when e.g. fetching them from the database.
In other words, SQLAlchemy internally is not invoking `__init__`.

## Decision

Writing custom `__init__` makes the most sense.

## Consequences

Whenever someone changes fields of a model (this should be rare after release), `__init__` needs to follow.
However, this inconvenience can be potentially automated away in the future. At least, we could also have a custom static code check that would guard that.  
