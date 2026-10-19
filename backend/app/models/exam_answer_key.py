from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ExamAnswerKey(Base):
    __tablename__ = "exam_answer_keys"

    __table_args__ = (
        UniqueConstraint(
            "section_id",
            "question_number",
            name="uq_exam_answer_keys_section_question",
        ),
        CheckConstraint(
            "question_number BETWEEN 1 AND 20",
            name="ck_exam_answer_keys_question_number",
        ),
        CheckConstraint(
            "correct_option BETWEEN 1 AND 5",
            name="ck_exam_answer_keys_correct_option",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    section_id: Mapped[int] = mapped_column(
        ForeignKey(
            "exam_sections.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    question_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    correct_option: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
