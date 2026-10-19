import pytest
import yaml

from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.content.demo import create_demo_exam
from app.content.importer import import_exam
from app.content.publisher import (
    PublicationError,
    publish_exam,
)
from app.db import Base, create_db_engine
from app.models import Exam, ExamAnswerKey


@pytest.fixture
def publisher_env(tmp_path):
    engine = create_db_engine(
        f"sqlite:///{tmp_path / 'publisher.db'}"
    )

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    source = tmp_path / "source"
    storage = tmp_path / "storage"

    create_demo_exam(source)

    # 자동 테스트에 사용할 별도 시험 코드
    manifest_path = source / "exam.yaml"
    manifest = yaml.safe_load(
        manifest_path.read_text(encoding="utf-8")
    )

    manifest["code"] = "test-exam-01"

    manifest_path.write_text(
        yaml.safe_dump(
            manifest,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    import_exam(
        source,
        session_factory=factory,
        storage_root=storage,
    )

    try:
        yield factory, storage
    finally:
        engine.dispose()


def publish(env, *, reviewed=True, code="test-exam-01"):
    factory, storage = env

    publish_exam(
        code,
        content_reviewed=reviewed,
        session_factory=factory,
        storage_root=storage,
    )


def get_status(env):
    factory, _ = env

    with factory() as db:
        exam = db.scalar(select(Exam))
        assert exam is not None
        return exam.status


def test_publish_valid_exam(publisher_env):
    assert get_status(publisher_env) == "DRAFT"

    publish(publisher_env)

    assert get_status(publisher_env) == "PUBLISHED"


def test_review_confirmation_required(publisher_env):
    with pytest.raises(PublicationError):
        publish(publisher_env, reviewed=False)

    assert get_status(publisher_env) == "DRAFT"


def test_demo_publication_blocked(publisher_env):
    with pytest.raises(PublicationError):
        publish(publisher_env, code="demo-exam-01")

    assert get_status(publisher_env) == "DRAFT"


def test_pdf_integrity_required(publisher_env):
    _, storage = publisher_env

    pdf_path = (
        storage
        / "test-exam-01"
        / "v1"
        / "questions.pdf"
    )

    with pdf_path.open("ab") as file:
        file.write(b"MODIFIED")

    with pytest.raises(PublicationError):
        publish(publisher_env)

    assert get_status(publisher_env) == "DRAFT"


def test_invalid_answers_block_publication(publisher_env):
    factory, _ = publisher_env

    with factory.begin() as db:
        answer = db.scalar(select(ExamAnswerKey))
        assert answer is not None

        answer.correct_option = (
            answer.correct_option % 5
        ) + 1

    with pytest.raises(PublicationError):
        publish(publisher_env)

    assert get_status(publisher_env) == "DRAFT"


def test_duplicate_publication_blocked(publisher_env):
    publish(publisher_env)

    with pytest.raises(PublicationError):
        publish(publisher_env)

    assert get_status(publisher_env) == "PUBLISHED"
