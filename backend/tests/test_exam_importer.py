import csv

import pytest
import yaml

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.content.demo import create_demo_exam
from app.content.importer import (
    ContentImportError,
    import_exam,
    verify_exam_pdf,
)
from app.db import Base, create_db_engine
from app.models import (
    Exam,
    ExamBook,
    ExamSection,
    ExamAnswerKey,
)


@pytest.fixture
def import_env(tmp_path):
    engine = create_db_engine(
        f"sqlite:///{tmp_path / 'import.db'}"
    )

    Base.metadata.create_all(engine)

    SessionFactory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    source = tmp_path / "source" / "demo-exam-01"
    storage = tmp_path / "storage"

    create_demo_exam(source)

    try:
        yield source, storage, SessionFactory
    finally:
        engine.dispose()


def run_import(env):
    source, storage, session_factory = env

    return import_exam(
        source,
        session_factory=session_factory,
        storage_root=storage,
    )


def test_import_exam(import_env):
    _, storage, session_factory = import_env

    result = run_import(import_env)

    assert result.code == "demo-exam-01"
    assert result.section_count == 5
    assert result.answer_count == 100
    assert len(result.pdf_sha256) == 64

    with session_factory() as db:
        exam = db.scalar(select(Exam))

        assert exam is not None
        assert exam.status == "DRAFT"
        assert exam.pdf_filename == "questions.pdf"
        assert verify_exam_pdf(exam, storage)

        assert db.scalar(
            select(func.count()).select_from(ExamBook)
        ) == 1

        assert db.scalar(
            select(func.count()).select_from(ExamSection)
        ) == 5

        assert db.scalar(
            select(func.count()).select_from(ExamAnswerKey)
        ) == 100


def test_duplicate_import_rejected(import_env):
    _, _, session_factory = import_env

    run_import(import_env)

    with pytest.raises(ContentImportError):
        run_import(import_env)

    with session_factory() as db:
        assert db.scalar(
            select(func.count()).select_from(Exam)
        ) == 1


def test_invalid_content_not_imported(import_env):
    source, storage, session_factory = import_env

    csv_path = source / "answers.csv"

    with csv_path.open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    rows.pop()

    with csv_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["section", "question", "answer"],
        )

        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ContentImportError):
        run_import(import_env)

    with session_factory() as db:
        assert db.scalar(
            select(func.count()).select_from(Exam)
        ) == 0

    assert not (
        storage / "demo-exam-01" / "v1"
    ).exists()


def test_pdf_integrity_check(import_env):
    _, storage, session_factory = import_env

    run_import(import_env)

    with session_factory() as db:
        exam = db.scalar(select(Exam))

        assert verify_exam_pdf(exam, storage)

        pdf_path = (
            storage
            / "demo-exam-01"
            / "v1"
            / "questions.pdf"
        )

        # 서버 보관 PDF를 임의 변경
        with pdf_path.open("ab") as file:
            file.write(b"MODIFIED")

        assert not verify_exam_pdf(exam, storage)


def test_existing_storage_rolls_back_database(import_env):
    _, storage, session_factory = import_env

    target = storage / "demo-exam-01" / "v1"
    target.mkdir(parents=True)

    # 기존 파일은 덮어쓰면 안 됨
    marker = target / "existing.txt"
    marker.write_text("KEEP", encoding="utf-8")

    with pytest.raises(ContentImportError):
        run_import(import_env)

    with session_factory() as db:
        assert db.scalar(
            select(func.count()).select_from(Exam)
        ) == 0

        assert db.scalar(
            select(func.count()).select_from(ExamBook)
        ) == 0

    assert marker.read_text(encoding="utf-8") == "KEEP"
