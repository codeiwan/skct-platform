import pytest

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import Base, create_db_engine, get_db
from app.main import app
from app.models import User
from app.security.passwords import verify_password


@pytest.fixture
def registration_env(tmp_path):
    database_file = tmp_path / "registration.db"

    engine = create_db_engine(
        f"sqlite:///{database_file}"
    )

    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    def override_get_db():
        with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, TestingSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def make_payload(skala_id="G051"):
    return {
        "skala_id": skala_id,
        "name": "테스트 사용자",
        "password": "TestPassword123!",
    }


def test_register_user(registration_env):
    client, session_factory = registration_env

    response = client.post(
        "/api/auth/register",
        json=make_payload(" G051 "),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] > 0
    assert data["skala_id"] == "G051"
    assert data["name"] == "테스트 사용자"
    assert data["status"] == "PENDING"

    assert "password" not in data
    assert "password_hash" not in data

    with session_factory() as session:
        user = session.scalar(
            select(User).where(
                User.skala_id_key == "g051"
            )
        )

        assert user is not None
        assert user.role == "USER"
        assert user.status == "PENDING"

        assert user.password_hash != "TestPassword123!"
        assert user.password_hash.startswith("$argon2id$")

        assert verify_password(
            "TestPassword123!",
            user.password_hash,
        )


def test_duplicate_skala_id(registration_env):
    client, session_factory = registration_env

    first = client.post(
        "/api/auth/register",
        json=make_payload("G051"),
    )

    assert first.status_code == 201

    duplicate = client.post(
        "/api/auth/register",
        json=make_payload(" g051 "),
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == (
        "이미 등록된 SKALA 고유번호입니다."
    )

    # 반려된 계정의 고유번호도 재사용할 수 없음
    with session_factory() as session:
        user = session.scalar(
            select(User).where(
                User.skala_id_key == "g051"
            )
        )

        user.status = "REJECTED"
        session.commit()

    duplicate_after_rejection = client.post(
        "/api/auth/register",
        json=make_payload("G051"),
    )

    assert duplicate_after_rejection.status_code == 409


def test_custom_skala_id_format(registration_env):
    client, _ = registration_env

    response = client.post(
        "/api/auth/register",
        json=make_payload("SKALA-2026-XYZ"),
    )

    assert response.status_code == 201
    assert response.json()["skala_id"] == "SKALA-2026-XYZ"


def test_invalid_registration_data(registration_env):
    client, _ = registration_env

    invalid_cases = [
        {"skala_id": "   "},
        {"skala_id": "A" * 65},
        {"name": "   "},
        {"password": "short"},
        {"password": "        "},
    ]

    for changes in invalid_cases:
        payload = make_payload()
        payload.update(changes)

        response = client.post(
            "/api/auth/register",
            json=payload,
        )

        assert response.status_code == 422


def test_cannot_assign_admin_role(registration_env):
    client, _ = registration_env

    payload = make_payload()
    payload["role"] = "ADMIN"
    payload["status"] = "ACTIVE"

    response = client.post(
        "/api/auth/register",
        json=payload,
    )

    assert response.status_code == 422
