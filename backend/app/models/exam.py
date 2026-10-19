from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ExamBook(Base):
    __tablename__ = "exam_books"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    publisher: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )


class Exam(Base):
    __tablename__ = "exams"

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')",
            name="ck_exams_status",
        ),
        CheckConstraint(
            "content_version >= 1",
            name="ck_exams_content_version",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    book_id: Mapped[int] = mapped_column(
        ForeignKey("exam_books.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="DRAFT",
        server_default="DRAFT",
    )

    content_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    pdf_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    pdf_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
