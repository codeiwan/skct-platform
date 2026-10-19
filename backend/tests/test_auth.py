from datetime import timedelta

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import Base, create_db_engine, get_db
from app.main import app
from app.models import AuthSession, User
from app.security.passwords import hash_password
from app.security.sessions import (
    COOKIE_NAME,
    hash_token,
    utc_now,
)


PASSWORD = "TestPassword123!"


@pytest.fixture
def auth_env(tmp_path):
    engine = create_db_engine(
        f"sqlite:///{tmp_path / 'auth.db'}"
    )

    Base.metadata.create_all(engine)

    SessionFactory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    def override_get_db():
        with SessionFactory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, SessionFactory
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def create_user(
    session_factory,
    status="ACTIVE",
):
    with session_factory() as db:
        user = User(
            skala_id="G051",
            name="테스트 사용자",
            password_hash=hash_password(PASSWORD),
            status=status,
        )

        db.add(user)
        db.commit()


def login(client):
    return client.post(
        "/api/auth/login",
        json={
            "skala_id": "g051",
            "password": PASSWORD,
        },
    )


def test_active_user_login(auth_env):
    client, session_factory = auth_env
    create_user(session_factory)

    response = login(client)

    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
    assert response.json()["role"] == "USER"

    assert "password" not in response.json()
    assert "password_hash" not in response.json()

    cookie_header = response.headers["set-cookie"].lower()

    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header

    token = client.cookies.get(COOKIE_NAME)

    assert token is not None

    with session_factory() as db:
        saved_session = db.scalar(select(AuthSession))

        assert saved_session is not None
        assert saved_session.token_hash == hash_token(token)
        assert saved_session.token_hash != token


def test_pending_user_cannot_login(auth_env):
    client, session_factory = auth_env
    create_user(session_factory, status="PENDING")

    response = login(client)

    assert response.status_code == 403

    with session_factory() as db:
        assert db.scalar(select(AuthSession)) is None


def test_invalid_password(auth_env):
    client, session_factory = auth_env
    create_user(session_factory)

    response = client.post(
        "/api/auth/login",
        json={
            "skala_id": "G051",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401


def test_login_me_and_logout(auth_env):
    client, session_factory = auth_env
    create_user(session_factory)

    assert login(client).status_code == 200

    me = client.get("/api/auth/me")

    assert me.status_code == 200
    assert me.json()["skala_id"] == "G051"

    # CSRF 없이 로그아웃 시도
    invalid_logout = client.post("/api/auth/logout")

    assert invalid_logout.status_code == 403

    csrf_response = client.get("/api/auth/csrf")

    assert csrf_response.status_code == 200

    csrf_token = csrf_response.json()["csrf_token"]

    logout_response = client.post(
        "/api/auth/logout",
        headers={
            "X-CSRF-Token": csrf_token,
        },
    )

    assert logout_response.status_code == 204

    # 로그아웃 후 인증 불가
    assert client.get("/api/auth/me").status_code == 401


def test_expired_session(auth_env):
    client, session_factory = auth_env
    create_user(session_factory)

    assert login(client).status_code == 200

    with session_factory() as db:
        saved_session = db.scalar(select(AuthSession))

        saved_session.expires_at = (
            utc_now() - timedelta(seconds=1)
        )

        db.commit()

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_session_renewal(auth_env):
    client, session_factory = auth_env
    create_user(session_factory)

    assert login(client).status_code == 200

    with session_factory() as db:
        saved_session = db.scalar(select(AuthSession))

        saved_session.expires_at = (
            utc_now() + timedelta(days=1)
        )

        db.commit()

    response = client.get("/api/auth/me")

    assert response.status_code == 200

    with session_factory() as db:
        renewed_session = db.scalar(select(AuthSession))

        assert renewed_session.expires_at > (
            utc_now() + timedelta(days=29)
        )
