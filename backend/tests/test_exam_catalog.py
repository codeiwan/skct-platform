import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db import Base, create_db_engine, get_db
from app.models import Exam, ExamBook, ExamSection

from app.api.exams import get_current_session


@pytest.fixture
def catalog_env(tmp_path):
    engine = create_db_engine(
        f"sqlite:///{tmp_path / 'catalog.db'}"
    )

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    def override_get_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(
            get_current_session,
            None,
        )
        engine.dispose()


def authenticate():
    # 시험 목록의 조회 동작을 독립적으로 검증하기 위해
    # 기존 로그인 의존성을 테스트에서만 대체합니다.
    app.dependency_overrides[
        get_current_session
    ] = lambda: object()


def seed_exams(factory):
    with factory.begin() as db:
        book = ExamBook(
            title="테스트 SKCT 문제집",
            publisher="테스트 출판사",
        )
        db.add(book)
        db.flush()

        for code, status in [
            ("draft-exam", "DRAFT"),
            ("published-exam", "PUBLISHED"),
            ("archived-exam", "ARCHIVED"),
        ]:
            exam = Exam(
                book_id=book.id,
                code=code,
                title=f"{code} 시험",
                status=status,
            )

            db.add(exam)
            db.flush()

            if status == "PUBLISHED":
                names = [
                    "언어이해",
                    "자료해석",
                    "창의수리",
                    "언어추리",
                    "수열추리",
                ]

                for number, name in enumerate(
                    names,
                    start=1,
                ):
                    db.add(
                        ExamSection(
                            exam_id=exam.id,
                            section_number=number,
                            section_type=name,
                            start_page=number,
                        )
                    )


def test_anonymous_access_denied(catalog_env):
    client, _ = catalog_env

    response = client.get("/api/exams")

    assert response.status_code == 401


def test_empty_published_catalog(catalog_env):
    client, _ = catalog_env
    authenticate()

    response = client.get("/api/exams")

    assert response.status_code == 200
    assert response.json() == []


def test_only_published_exams_returned(catalog_env):
    client, factory = catalog_env
    authenticate()
    seed_exams(factory)

    response = client.get("/api/exams")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["code"] == "published-exam"
    assert data[0]["book_title"] == "테스트 SKCT 문제집"


def test_exam_section_summary(catalog_env):
    client, factory = catalog_env
    authenticate()
    seed_exams(factory)

    response = client.get("/api/exams")

    assert response.status_code == 200

    exam = response.json()[0]

    assert exam["total_questions"] == 100
    assert exam["total_duration_seconds"] == 4500

    assert len(exam["sections"]) == 5
    assert [
        section["section_type"]
        for section in exam["sections"]
    ] == [
        "언어이해",
        "자료해석",
        "창의수리",
        "언어추리",
        "수열추리",
    ]


def test_sensitive_fields_not_exposed(catalog_env):
    client, factory = catalog_env
    authenticate()
    seed_exams(factory)

    response = client.get("/api/exams")

    assert response.status_code == 200

    payload = response.text

    for forbidden in (
        "correct_option",
        "pdf_filename",
        "pdf_sha256",
        "start_page",
        "password_hash",
        "section_id",
    ):
        assert forbidden not in payload