import uuid
from typing import Any

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    Source: https://docs.sqlalchemy.org/en/13/core/
    custom_types.html#backend-agnostic-guid-type
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if dialect.name == "postgresql":
            return str(value)
        elif not isinstance(value, uuid.UUID):  # pragma: no cover
            return uuid.UUID(value).hex
        else:
            # hexstring
            return value.hex

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if isinstance(value, uuid.UUID):
            return value
        else:
            return uuid.UUID(value)
