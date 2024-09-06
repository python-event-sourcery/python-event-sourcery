import json
from typing import Any

from sqlalchemy.dialects.postgresql import JSONB as POSTGRES_JSONB
from sqlalchemy.types import Text, TypeDecorator


class JSONB(TypeDecorator):
    impl = Text

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(POSTGRES_JSONB())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect: Any) -> Any | None:
        if dialect.name == "postgresql":
            return value
        else:
            return json.dumps(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any | None:
        if dialect.name == "postgresql":
            return value
        else:
            return json.loads(value)
