import pytest

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base, create_db_engine
from app.models import Exam, ExamBook


@pytest.fixture
def db_session(tmp_path):
    engine = create_db_engine(
        f"sqlite:///{tmp_path / 'exams.db'}"
    )

    Base.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def create_book(db: Session) -> ExamBook:
    book = ExamBook(
        title="DEMO SKCT 통합기본서",
        publisher="테스트 출판사",
    )

    db.add(book)
    db.commit()
    db.refresh(book)

    return book


def test_create_exam_book(db_session):
    book = create_book(db_session)

    assert book.id is not None
    assert book.title == "DEMO SKCT 통합기본서"
    assert book.created_at is not None


def test_create_draft_exam(db_session):
    book = create_book(db_session)

    exam = Exam(
        book_id=book.id,
        code="demo-mock-01",
        title="실전 모의고사 1회",
    )

    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    assert exam.id is not None
    assert exam.book_id == book.id
    assert exam.status == "DRAFT"
    assert exam.content_version == 1
    assert exam.pdf_filename is None


def test_duplicate_exam_code(db_session):
    book = create_book(db_session)

    first = Exam(
        book_id=book.id,
        code="demo-mock-01",
        title="실전 모의고사 1회",
    )

    db_session.add(first)
    db_session.commit()

    second = Exam(
        book_id=book.id,
        code="demo-mock-01",
        title="실전 모의고사 2회",
    )

    db_session.add(second)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_invalid_exam_status(db_session):
    book = create_book(db_session)

    exam = Exam(
        book_id=book.id,
        code="demo-mock-02",
        title="실전 모의고사 2회",
        status="INVALID",
    )

    db_session.add(exam)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_invalid_book_reference(db_session):
    exam = Exam(
        book_id=999999,
        code="demo-mock-03",
        title="실전 모의고사 3회",
    )

    db_session.add(exam)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
