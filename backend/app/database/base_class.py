from typing import Any
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    id: Any
    __name__: str

    # Generate __tablename__ automatically
    @declared_attr
    def __tablename__(cls) -> str:
        # Convert class name from CamelCase to snake_case
        name = cls.__name__
        parts = []
        start = 0
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                parts.append(name[start:i].lower())
                start = i
        parts.append(name[start:].lower())
        return "_".join(parts)
