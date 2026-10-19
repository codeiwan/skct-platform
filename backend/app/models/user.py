from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db import Base


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint(
            "skala_id_key",
            name="uq_users_skala_id_key",
        ),
        CheckConstraint(
            "role IN ('USER', 'ADMIN')",
            name="ck_users_role",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'REJECTED')",
            name="ck_users_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    skala_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    skala_id_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="USER",
        server_default="USER",
    )

    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    @validates("skala_id")
    def validate_skala_id(self, key: str, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("SKALA 고유번호는 문자열이어야 합니다.")

        value = value.strip()
        normalized = value.casefold()

        if not value or len(value) > 64 or len(normalized) > 64:
            raise ValueError(
                "SKALA 고유번호는 1~64자로 입력해야 합니다."
            )

        self.skala_id_key = normalized

        return value

    @validates("name")
    def validate_name(self, key: str, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("이름은 문자열이어야 합니다.")

        value = value.strip()

        if not value or len(value) > 100:
            raise ValueError(
                "이름은 1~100자로 입력해야 합니다."
            )

        return value
