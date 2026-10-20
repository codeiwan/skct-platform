
import pytest

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db import Base, create_db_engine, get_db
from app.models import Exam, ExamBook
from app.security.sessions import get_current_session
from app.api.exams import get_exam_storage_root
from app.content.importer import sha256_file


@pytest.fixture
def pdf_env(tmp_path):
    engine = create_db_engine(
        f"sqlite:///{tmp_path / 'pdf_api.db'}"
    )

    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    storage_root = tmp_path / "exam_packages"

    # 테스트용 PDF 및 시험 데이터 생성
    with factory.begin() as db:
        book = ExamBook(
            title="테스트 SKCT 문제집",
            publisher="테스트 출판사",
        )

        db.add(book)
        db.flush()

        for code, status in [
            ("published-exam", "PUBLISHED"),
            ("draft-exam", "DRAFT"),
            ("archived-exam", "ARCHIVED"),
        ]:
            pdf_path = (
                storage_root
                / code
                / "v1"
                / "questions.pdf"
            )

            pdf_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            writer = PdfWriter()
            writer.add_blank_page(
                width=595,
                height=842,
            )
            writer.write(str(pdf_path))

            db.add(
                Exam(
                    book_id=book.id,
                    code=code,
                    title=f"{code} 시험",
                    status=status,
                    content_version=1,
                    pdf_filename="questions.pdf",
                    pdf_sha256=sha256_file(pdf_path),
                )
            )

    def override_get_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    app.dependency_overrides[
        get_exam_storage_root
    ] = lambda: storage_root

    try:
        with TestClient(app) as client:
            yield client, factory, storage_root

    finally:
        app.dependency_overrides.pop(get_db, None)

        app.dependency_overrides.pop(
            get_current_session,
            None,
        )

        app.dependency_overrides.pop(
            get_exam_storage_root,
            None,
        )

        engine.dispose()


def authenticate():
    app.dependency_overrides[
        get_current_session
    ] = lambda: object()


def test_published_pdf_download(pdf_env):
    client, _, _ = pdf_env
    authenticate()

    response = client.get(
        "/api/exams/published-exam/pdf"
    )

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-type"].startswith(
        "application/pdf"
    )
    assert "inline" in response.headers[
        "content-disposition"
    ]
    assert "no-store" in response.headers[
        "cache-control"
    ]
    assert response.headers[
        "x-content-type-options"
    ] == "nosniff"


def test_anonymous_pdf_denied(pdf_env):
    client, _, _ = pdf_env

    response = client.get(
        "/api/exams/published-exam/pdf"
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "code",
    [
        "draft-exam",
        "archived-exam",
        "missing-exam",
    ],
)
def test_unavailable_pdf_returns_404(pdf_env, code):
    client, _, _ = pdf_env
    authenticate()

    response = client.get(
        f"/api/exams/{code}/pdf"
    )

    assert response.status_code == 404


def test_missing_pdf_blocked(pdf_env):
    client, _, storage = pdf_env
    authenticate()

    pdf_path = (
        storage
        / "published-exam"
        / "v1"
        / "questions.pdf"
    )

    pdf_path.unlink()

    response = client.get(
        "/api/exams/published-exam/pdf"
    )

    assert response.status_code == 503


def test_modified_pdf_blocked(pdf_env):
    client, _, storage = pdf_env
    authenticate()

    pdf_path = (
        storage
        / "published-exam"
        / "v1"
        / "questions.pdf"
    )

    with pdf_path.open("ab") as file:
        file.write(b"MODIFIED")

    response = client.get(
        "/api/exams/published-exam/pdf"
    )

    assert response.status_code == 503


def test_missing_checksum_blocked(pdf_env):
    client, factory, _ = pdf_env
    authenticate()

    with factory.begin() as db:
        exam = db.scalar(
            select(Exam).where(
                Exam.code == "published-exam"
            )
        )

        assert exam is not None
        exam.pdf_sha256 = None

    response = client.get(
        "/api/exams/published-exam/pdf"
    )

    assert response.status_code == 503


def test_pdf_range_request(pdf_env):
    client, _, _ = pdf_env
    authenticate()

    response = client.get(
        "/api/exams/published-exam/pdf",
        headers={
            "Range": "bytes=0-3",
        },
    )

    assert response.status_code == 206
    assert response.content == b"%PDF"
    assert response.headers["content-range"].startswith(
        "bytes 0-3/"
    )
