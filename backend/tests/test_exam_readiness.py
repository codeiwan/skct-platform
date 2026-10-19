import pytest

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.content.demo import create_demo_exam
from app.content.importer import import_exam
from app.content.readiness import check_exam_readiness
from app.db import Base, create_db_engine
from app.models import (
    Exam,
    ExamSection,
    ExamAnswerKey,
)


@pytest.fixture
def readiness_env(tmp_path):
    engine = create_db_engine(
        f"sqlite:///{tmp_path / 'readiness.db'}"
    )

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    source = tmp_path / "source" / "demo-exam-01"
    storage = tmp_path / "storage"

    create_demo_exam(source)

    import_exam(
        source,
        session_factory=factory,
        storage_root=storage,
    )

    try:
        yield factory, storage
    finally:
        engine.dispose()


def check(env, code="demo-exam-01"):
    factory, storage = env

    return check_exam_readiness(
        code,
        session_factory=factory,
        storage_root=storage,
    )


def test_valid_exam_ready(readiness_env):
    result = check(readiness_env)

    assert result.ready
    assert result.errors == ()


def test_unknown_exam_not_ready(readiness_env):
    result = check(readiness_env, "unknown-exam")

    assert not result.ready
    assert any("찾을 수 없습니다" in e for e in result.errors)


def test_missing_pdf_not_ready(readiness_env):
    _, storage = readiness_env

    pdf = storage / "demo-exam-01" / "v1" / "questions.pdf"
    pdf.unlink()

    result = check(readiness_env)

    assert not result.ready
    assert any("PDF" in e for e in result.errors)


def test_modified_pdf_not_ready(readiness_env):
    _, storage = readiness_env

    pdf = storage / "demo-exam-01" / "v1" / "questions.pdf"

    with pdf.open("ab") as file:
        file.write(b"MODIFIED")

    result = check(readiness_env)

    assert not result.ready
    assert any("SHA-256" in e for e in result.errors)


def test_missing_answer_not_ready(readiness_env):
    factory, _ = readiness_env

    with factory.begin() as db:
        answer = db.scalar(select(ExamAnswerKey))
        assert answer is not None
        db.delete(answer)

    result = check(readiness_env)

    assert not result.ready
    assert any("100개" in e for e in result.errors)


def test_changed_answer_not_ready(readiness_env):
    factory, _ = readiness_env

    with factory.begin() as db:
        answer = db.scalar(select(ExamAnswerKey))
        assert answer is not None

        answer.correct_option = (
            answer.correct_option % 5
        ) + 1

    result = check(readiness_env)

    assert not result.ready
    assert any("CSV" in e for e in result.errors)


def test_changed_section_not_ready(readiness_env):
    factory, _ = readiness_env

    with factory.begin() as db:
        section = db.scalar(
            select(ExamSection).where(
                ExamSection.section_number == 5
            )
        )

        assert section is not None
        section.start_page = 999

    result = check(readiness_env)

    assert not result.ready
    assert any("YAML" in e for e in result.errors)


def test_archived_exam_not_ready(readiness_env):
    factory, _ = readiness_env

    with factory.begin() as db:
        exam = db.scalar(select(Exam))
        assert exam is not None

        exam.status = "ARCHIVED"

    result = check(readiness_env)

    assert not result.ready
    assert any("DRAFT" in e for e in result.errors)
