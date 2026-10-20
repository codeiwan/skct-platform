import re
from collections import defaultdict
from pathlib import Path

from app.content.importer import STORAGE_ROOT, package_path, verify_exam_pdf
from app.db import get_db
from app.models import Exam, ExamBook, ExamSection
from app.security.sessions import get_current_session

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_exam_storage_root() -> Path:
    return STORAGE_ROOT


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


@router.get(
    "/{exam_code}/pdf",
    response_class=FileResponse,
    responses={
        200: {
            "content": {
                "application/pdf": {},
            },
            "description": "인증된 사용자의 시험 PDF 열람",
        },
        401: {"description": "로그인 필요"},
        404: {"description": "공개된 시험 없음"},
        503: {"description": "PDF 무결성 오류"},
    },
)
def get_exam_pdf(
    exam_code: str,
    db: Session = Depends(get_db),
    _session=Depends(get_current_session),
    storage_root: Path = Depends(get_exam_storage_root),
) -> FileResponse:

    # 공개된 시험만 조회
    exam = db.scalar(
        select(Exam).where(
            Exam.code == exam_code,
            Exam.status == "PUBLISHED",
        )
    )

    if exam is None:
        raise HTTPException(
            status_code=404,
            detail="시험을 찾을 수 없습니다.",
        )

    # 서버 보관 경로에 사용할 코드 검증
    if re.fullmatch(
        r"[a-z0-9][a-z0-9_-]{0,63}",
        exam.code,
    ) is None:
        raise HTTPException(
            status_code=503,
            detail="시험 PDF를 사용할 수 없습니다.",
        )

    # 파일 존재 여부와 SHA-256 무결성 확인
    try:
        pdf_valid = verify_exam_pdf(
            exam,
            storage_root,
        )
    except OSError:
        pdf_valid = False

    if not pdf_valid:
        raise HTTPException(
            status_code=503,
            detail="시험 PDF를 사용할 수 없습니다.",
        )

    pdf_path = package_path(
        exam,
        storage_root,
    )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename="questions.pdf",
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "X-Content-Type-Options": "nosniff",
        },
    )
