import pytest

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base, create_db_engine
from app.models import (
    Exam,
    ExamBook,
    ExamSection,
    ExamAnswerKey,
)


SECTION_TYPES = [
    "언어이해",
    "자료해석",
    "창의수리",
    "언어추리",
    "수열추리",
]


@pytest.fixture
def db_session(tmp_path):
    engine = create_db_engine(
        f"sqlite:///{tmp_path / 'exam_sections.db'}"
    )

    Base.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def create_exam(db: Session) -> Exam:
    book = ExamBook(
        title="DEMO SKCT 문제집",
        publisher="테스트 전용",
    )

    db.add(book)
    db.flush()

    exam = Exam(
        book_id=book.id,
        code="demo-exam-01",
        title="DEMO 모의고사 1회",
    )

    db.add(exam)
    db.commit()
    db.refresh(exam)

    return exam


def make_section(exam_id: int, **changes) -> ExamSection:
    data = {
        "exam_id": exam_id,
        "section_number": 1,
        "section_type": "언어이해",
        "start_page": 2,
    }

    data.update(changes)

    return ExamSection(**data)


def test_create_five_sections_and_100_keys(db_session):
    exam = create_exam(db_session)

    sections = [
        ExamSection(
            exam_id=exam.id,
            section_number=index,
            section_type=section_type,
            start_page=2 + (index - 1) * 8,
        )
        for index, section_type in enumerate(
            SECTION_TYPES,
            start=1,
        )
    ]

    db_session.add_all(sections)
    db_session.flush()

    answer_keys = [
        ExamAnswerKey(
            section_id=section.id,
            question_number=question,
            correct_option=(question - 1) % 5 + 1,
        )
        for section in sections
        for question in range(1, 21)
    ]

    db_session.add_all(answer_keys)
    db_session.commit()

    section_count = db_session.scalar(
        select(func.count()).select_from(ExamSection)
    )

    answer_count = db_session.scalar(
        select(func.count()).select_from(ExamAnswerKey)
    )

    assert section_count == 5
    assert answer_count == 100

    for section in sections:
        assert section.question_count == 20
        assert section.duration_seconds == 900


def test_duplicate_section(db_session):
    exam = create_exam(db_session)

    db_session.add(make_section(exam.id))
    db_session.commit()

    db_session.add(make_section(exam.id))

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


@pytest.mark.parametrize(
    "changes",
    [
        {"start_page": 0},
        {"question_count": 19},
        {"duration_seconds": 901},
        {"section_number": 0},
        {"section_type": "자료해석"},
        {
            "section_number": 6,
            "section_type": "수열추리",
        },
    ],
)
def test_invalid_section_configuration(db_session, changes):
    exam = create_exam(db_session)

    db_session.add(
        make_section(exam.id, **changes)
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_duplicate_answer_key(db_session):
    exam = create_exam(db_session)

    section = make_section(exam.id)
    db_session.add(section)
    db_session.flush()

    db_session.add(
        ExamAnswerKey(
            section_id=section.id,
            question_number=1,
            correct_option=3,
        )
    )

    db_session.commit()

    db_session.add(
        ExamAnswerKey(
            section_id=section.id,
            question_number=1,
            correct_option=5,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


@pytest.mark.parametrize(
    "question_number,correct_option",
    [
        (0, 3),
        (21, 3),
        (1, 0),
        (1, 6),
    ],
)
def test_invalid_answer_key(
    db_session,
    question_number,
    correct_option,
):
    exam = create_exam(db_session)

    section = make_section(exam.id)
    db_session.add(section)
    db_session.flush()

    db_session.add(
        ExamAnswerKey(
            section_id=section.id,
            question_number=question_number,
            correct_option=correct_option,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_invalid_section_reference(db_session):
    db_session.add(
        ExamAnswerKey(
            section_id=999999,
            question_number=1,
            correct_option=3,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_incomplete_draft_allowed(db_session):
    exam = create_exam(db_session)

    section = make_section(exam.id)
    db_session.add(section)
    db_session.commit()

    assert exam.status == "DRAFT"

    answer_count = db_session.scalar(
        select(func.count()).select_from(ExamAnswerKey)
    )

    assert answer_count == 0
