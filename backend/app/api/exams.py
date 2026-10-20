from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Exam, ExamBook, ExamSection

from app.security.sessions import get_current_session


router = APIRouter(
    prefix="/api/exams",
    tags=["exams"],
)


class ExamSectionSummary(BaseModel):
    section_number: int
    section_type: str
    question_count: int
    duration_seconds: int


class ExamCatalogItem(BaseModel):
    code: str
    title: str
    book_title: str
    publisher: str | None
    total_questions: int
    total_duration_seconds: int
    sections: list[ExamSectionSummary]


class ExamDetailSection(BaseModel):
    section_number: int
    section_type: str
    start_page: int
    question_count: int
    duration_seconds: int


class ExamDetail(BaseModel):
    code: str
    title: str
    book_title: str
    publisher: str | None
    content_version: int
    total_questions: int
    total_duration_seconds: int
    sections: list[ExamDetailSection]


@router.get(
    "",
    response_model=list[ExamCatalogItem],
)
def list_published_exams(
    db: Session = Depends(get_db),
    _session=Depends(get_current_session),
) -> list[ExamCatalogItem]:

    rows = db.execute(
        select(Exam, ExamBook)
        .join(ExamBook, Exam.book_id == ExamBook.id)
        .where(Exam.status == "PUBLISHED")
        .order_by(Exam.id.desc())
    ).all()

    if not rows:
        return []

    exam_ids = [
        exam.id
        for exam, _ in rows
    ]

    sections = db.scalars(
        select(ExamSection)
        .where(ExamSection.exam_id.in_(exam_ids))
        .order_by(
            ExamSection.exam_id,
            ExamSection.section_number,
        )
    ).all()

    sections_by_exam = defaultdict(list)

    for section in sections:
        sections_by_exam[section.exam_id].append(
            ExamSectionSummary(
                section_number=section.section_number,
                section_type=section.section_type,
                question_count=section.question_count,
                duration_seconds=section.duration_seconds,
            )
        )

    results = []

    for exam, book in rows:
        exam_sections = sections_by_exam[exam.id]

        results.append(
            ExamCatalogItem(
                code=exam.code,
                title=exam.title,
                book_title=book.title,
                publisher=book.publisher,
                total_questions=sum(
                    section.question_count
                    for section in exam_sections
                ),
                total_duration_seconds=sum(
                    section.duration_seconds
                    for section in exam_sections
                ),
                sections=exam_sections,
            )
        )

    return results


@router.get(
    "/{exam_code}",
    response_model=ExamDetail,
)
def get_exam_detail(
    exam_code: str,
    db: Session = Depends(get_db),
    _session=Depends(get_current_session),
) -> ExamDetail:

    row = db.execute(
        select(Exam, ExamBook)
        .join(ExamBook, Exam.book_id == ExamBook.id)
        .where(
            Exam.code == exam_code,
            Exam.status == "PUBLISHED",
        )
    ).one_or_none()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="시험을 찾을 수 없습니다.",
        )

    exam, book = row

    sections = db.scalars(
        select(ExamSection)
        .where(ExamSection.exam_id == exam.id)
        .order_by(ExamSection.section_number)
    ).all()

    detail_sections = [
        ExamDetailSection(
            section_number=section.section_number,
            section_type=section.section_type,
            start_page=section.start_page,
            question_count=section.question_count,
            duration_seconds=section.duration_seconds,
        )
        for section in sections
    ]

    return ExamDetail(
        code=exam.code,
        title=exam.title,
        book_title=book.title,
        publisher=book.publisher,
        content_version=exam.content_version,
        total_questions=sum(
            section.question_count
            for section in detail_sections
        ),
        total_duration_seconds=sum(
            section.duration_seconds
            for section in detail_sections
        ),
        sections=detail_sections,
    )
