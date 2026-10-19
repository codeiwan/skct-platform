from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ExamSection(Base):
    __tablename__ = "exam_sections"

    __table_args__ = (
        UniqueConstraint(
            "exam_id",
            "section_number",
            name="uq_exam_sections_exam_number",
        ),
        UniqueConstraint(
            "exam_id",
            "section_type",
            name="uq_exam_sections_exam_type",
        ),
        CheckConstraint(
            "start_page >= 1",
            name="ck_exam_sections_start_page",
        ),
        CheckConstraint(
            "question_count = 20",
            name="ck_exam_sections_question_count",
        ),
        CheckConstraint(
            "duration_seconds = 900",
            name="ck_exam_sections_duration",
        ),
        CheckConstraint(
            """
            (section_number = 1 AND section_type = '언어이해')
            OR
            (section_number = 2 AND section_type = '자료해석')
            OR
            (section_number = 3 AND section_type = '창의수리')
            OR
            (section_number = 4 AND section_type = '언어추리')
            OR
            (section_number = 5 AND section_type = '수열추리')
            """,
            name="ck_exam_sections_type_order",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    section_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    section_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    start_page: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    question_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=20,
        server_default="20",
    )

    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=900,
        server_default="900",
    )
