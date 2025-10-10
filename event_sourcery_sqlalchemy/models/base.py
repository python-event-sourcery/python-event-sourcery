from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    ColumnElement,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    and_,
    true,
)
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.ext.hybrid import Comparator, hybrid_property
from sqlalchemy.orm import (
    Composite,
    InstrumentedAttribute,
    Mapped,
    MappedColumn,
    declared_attr,
    mapped_column,
    relationship,
)

from event_sourcery.event_store.backend import TenantId
from event_sourcery.event_store.stream import StreamId
from event_sourcery_sqlalchemy.guid import GUID
from event_sourcery_sqlalchemy.jsonb import JSONB


class StreamIdComparator(Comparator[StreamId]):
    def __init__(
        self,
        uuid: InstrumentedAttribute,
        name: InstrumentedAttribute,
        category: InstrumentedAttribute,
    ) -> None:
        super().__init__(Composite(uuid, name, category))

    def __eq__(self, other: Any) -> bool:  # type: ignore
        uuid, name, category = cast(Composite, self.__clause_element__()).attrs
        same_uuid = cast(ColumnElement[bool], uuid == other)
        same_name = cast(
            ColumnElement[bool], name == other.name if other.name else true()
        )
        same_category = cast(ColumnElement[bool], category == (other.category or ""))
        return and_(same_uuid, same_name, same_category)  # type: ignore


class BaseStream:
    __event_model__: type["BaseEvent"]
    __snapshot_model__: type["BaseSnapshot"]

    @declared_attr  # type: ignore[arg-type]
    @classmethod
    def __table_args__(cls) -> tuple[Index | UniqueConstraint, ...]:
        return (
            UniqueConstraint("uuid", "category", "tenant_id"),
            UniqueConstraint("name", "category", "tenant_id"),
        )

    id = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    uuid = mapped_column(GUID(), nullable=False)
    name = mapped_column(String(255), nullable=True, default=None)
    category = mapped_column(String(255), nullable=False, default="")
    tenant_id = mapped_column(String(255), nullable=False)
    version = mapped_column(BigInteger(), nullable=True)

    @classmethod
    def __set_mapping_information__(
        cls, event_model: type["BaseEvent"], snapshot_model: type["BaseSnapshot"]
    ) -> None:
        cls.__event_model__ = event_model
        cls.__snapshot_model__ = snapshot_model

    @declared_attr
    @classmethod
    def events(cls) -> Mapped[list["BaseEvent"]]:
        return relationship(cls.__event_model__, back_populates="stream")

    @declared_attr
    @classmethod
    def snapshots(cls) -> Mapped[list["BaseSnapshot"]]:
        return relationship(cls.__snapshot_model__, back_populates="stream")

    @hybrid_property
    def stream_id(self) -> StreamId:
        return StreamId(self.uuid, self.name, category=self.category or None)

    @stream_id.inplace.comparator
    @classmethod
    def _stream_id_comparator(cls) -> StreamIdComparator:
        return StreamIdComparator(cls.uuid, cls.name, cls.category)


class BaseEvent:
    __stream_model__: type["BaseStream"]
    __tablename__: str

    @declared_attr  # type: ignore[arg-type]
    @classmethod
    def __table_args__(cls) -> tuple[Index | UniqueConstraint, ...]:
        return (
            Index(
                f"ix_events_stream_id_version_{cls.__tablename__}",
                "db_stream_id",
                "version",
                unique=True,
            ),
        )

    def __init__(
        self,
        uuid: UUID,
        created_at: datetime,
        name: str,
        data: dict,
        event_context: dict,
        version: int | None,
    ) -> None:
        self.uuid = uuid
        self.created_at = created_at
        self.name = name
        self.data = data
        self.event_context = event_context
        self.version = version

    @classmethod
    def __set_mapping_information__(cls, stream_model: type[BaseStream]) -> None:
        cls.__stream_model__ = stream_model

    @declared_attr
    @classmethod
    def _db_stream_id(cls) -> MappedColumn[Any]:
        return mapped_column(
            "db_stream_id",
            BigInteger().with_variant(Integer(), "sqlite"),
            ForeignKey(cls.__stream_model__.id),
            nullable=False,
            index=True,
        )

    @declared_attr
    @classmethod
    def stream(cls) -> Mapped[BaseStream]:
        return relationship(cls.__stream_model__, back_populates="events")

    id = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    version = mapped_column(Integer(), nullable=True)
    uuid = mapped_column(GUID(), index=True, unique=True)
    stream_id: AssociationProxy[StreamId] = association_proxy("stream", "stream_id")
    tenant_id: AssociationProxy[TenantId] = association_proxy("stream", "tenant_id")
    name = mapped_column(String(200), nullable=False)
    data = mapped_column(JSONB(), nullable=False)
    event_context = mapped_column(JSONB(), nullable=False)
    created_at = mapped_column(DateTime(), nullable=False, index=True)


class BaseSnapshot:
    __stream_model__: type["BaseStream"]

    def __init__(
        self,
        uuid: UUID,
        created_at: datetime,
        name: str,
        data: dict,
        event_context: dict,
        version: int | None,
    ) -> None:
        self.uuid = uuid
        self.created_at = created_at
        self.name = name
        self.data = data
        self.event_context = event_context
        self.version = version

    @classmethod
    def __set_mapping_information__(cls, stream_model: type[BaseStream]) -> None:
        cls.__stream_model__ = stream_model

    @declared_attr
    @classmethod
    def _db_stream_id(cls) -> MappedColumn[Any]:
        return mapped_column(
            "db_stream_id",
            BigInteger().with_variant(Integer(), "sqlite"),
            ForeignKey(cls.__stream_model__.id),
            nullable=False,
            index=True,
        )

    @declared_attr
    @classmethod
    def stream(cls) -> Mapped[BaseStream]:
        return relationship(cls.__stream_model__, back_populates="snapshots")

    uuid = mapped_column(GUID, primary_key=True)
    version = mapped_column(Integer(), nullable=False)
    stream_id: AssociationProxy[StreamId] = association_proxy("stream", "stream_id")
    name = mapped_column(String(50), nullable=False)
    data = mapped_column(JSONB(), nullable=False)
    event_context = mapped_column(JSONB(), nullable=False)
    created_at = mapped_column(DateTime(), nullable=False)


class BaseOutboxEntry:
    id = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    created_at = mapped_column(DateTime(), nullable=False, index=True)
    data = mapped_column(JSONB(), nullable=False)
    stream_name = mapped_column(String(255), nullable=True)
    position = mapped_column(BigInteger().with_variant(Integer(), "sqlite"))
    tries_left = mapped_column(Integer(), nullable=False)


class BaseProjectorCursor:
    __tablename__: str

    @declared_attr  # type: ignore[arg-type]
    @classmethod
    def __table_args__(cls) -> tuple[Index | UniqueConstraint, ...]:
        return (
            Index(
                f"ix_name_stream_id_{cls.__tablename__}",
                "name",
                "stream_id",
                "category",
                unique=True,
            ),
        )

    id = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    name = mapped_column(String(255), nullable=False)
    stream_id = mapped_column(GUID(), nullable=False, index=True)
    category = mapped_column(String(255), nullable=True)
    version = mapped_column(BigInteger(), nullable=False)
