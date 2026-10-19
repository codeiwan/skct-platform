import pytest

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.cli import create_admin
from app.db import Base, create_db_engine, get_db
from app.main import app
from app.models import User
from app.security.passwords import hash_password, verify_password


PASSWORD = "TestPassword123!"


@pytest.fixture
def admin_env(tmp_path):
    engine = create_db_engine(
        f"sqlite:///{tmp_path / 'admin.db'}"
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


def seed_user(
    session_factory,
    skala_id: str,
    role: str = "USER",
    status: str = "PENDING",
) -> int:

    with session_factory() as db:
        user = User(
            skala_id=skala_id,
            name="테스트 사용자",
            password_hash=hash_password(PASSWORD),
            role=role,
            status=status,
        )

        db.add(user)
        db.commit()

        return user.id


def login(client, skala_id: str):
    return client.post(
        "/api/auth/login",
        json={
            "skala_id": skala_id,
            "password": PASSWORD,
        },
    )


def get_csrf(client) -> str:
    response = client.get("/api/auth/csrf")

    assert response.status_code == 200

    return response.json()["csrf_token"]


def test_create_admin_cli(admin_env, monkeypatch):
    _, session_factory = admin_env

    monkeypatch.setattr(
        create_admin,
        "SessionLocal",
        session_factory,
    )

    answers = iter(["ADMIN001", "테스트 관리자"])

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: next(answers),
    )

    monkeypatch.setattr(
        create_admin.getpass,
        "getpass",
        lambda prompt: PASSWORD,
    )

    assert create_admin.main() == 0

    with session_factory() as db:
        admin = db.scalar(
            select(User).where(
                User.skala_id_key == "admin001"
            )
        )

        assert admin is not None
        assert admin.role == "ADMIN"
        assert admin.status == "ACTIVE"
        assert admin.password_hash.startswith("$argon2id$")
        assert verify_password(
            PASSWORD,
            admin.password_hash,
        )


def test_pending_list_requires_admin(admin_env):
    client, session_factory = admin_env

    seed_user(session_factory, "ADMIN001", "ADMIN", "ACTIVE")
    seed_user(session_factory, "G051", "USER", "PENDING")
    seed_user(session_factory, "G052", "USER", "ACTIVE")

    # 로그인하지 않은 사용자
    response = client.get("/api/admin/users/pending")
    assert response.status_code == 401

    # 로그인한 일반 사용자
    assert login(client, "G052").status_code == 200

    response = client.get("/api/admin/users/pending")
    assert response.status_code == 403

    # 관리자 로그인
    assert login(client, "ADMIN001").status_code == 200

    response = client.get("/api/admin/users/pending")

    assert response.status_code == 200

    users = response.json()

    assert len(users) == 1
    assert users[0]["skala_id"] == "G051"
    assert "password_hash" not in users[0]
    assert "created_at" in users[0]


def test_approve_user_and_login(admin_env):
    client, session_factory = admin_env

    seed_user(session_factory, "ADMIN001", "ADMIN", "ACTIVE")
    user_id = seed_user(
        session_factory,
        "G051",
        "USER",
        "PENDING",
    )

    # 승인 전 로그인 차단
    assert login(client, "G051").status_code == 403

    # 관리자 로그인
    assert login(client, "ADMIN001").status_code == 200

    csrf_token = get_csrf(client)

    response = client.post(
        f"/api/admin/users/{user_id}/approve",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"

    # 승인 완료 후 로그인 허용
    assert login(client, "G051").status_code == 200

    me = client.get("/api/auth/me")

    assert me.status_code == 200
    assert me.json()["skala_id"] == "G051"
    assert me.json()["status"] == "ACTIVE"


def test_reject_user(admin_env):
    client, session_factory = admin_env

    seed_user(session_factory, "ADMIN001", "ADMIN", "ACTIVE")
    user_id = seed_user(
        session_factory,
        "G051",
        "USER",
        "PENDING",
    )

    assert login(client, "ADMIN001").status_code == 200

    csrf_token = get_csrf(client)

    response = client.post(
        f"/api/admin/users/{user_id}/reject",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"

    assert login(client, "G051").status_code == 403

    with session_factory() as db:
        user = db.get(User, user_id)
        assert user.status == "REJECTED"


def test_admin_actions_require_csrf(admin_env):
    client, session_factory = admin_env

    seed_user(session_factory, "ADMIN001", "ADMIN", "ACTIVE")
    user_id = seed_user(
        session_factory,
        "G051",
        "USER",
        "PENDING",
    )

    assert login(client, "ADMIN001").status_code == 200

    # CSRF 토큰 누락
    response = client.post(
        f"/api/admin/users/{user_id}/approve"
    )

    assert response.status_code == 403

    # 잘못된 CSRF 토큰
    response = client.post(
        f"/api/admin/users/{user_id}/approve",
        headers={"X-CSRF-Token": "invalid-token"},
    )

    assert response.status_code == 403

    with session_factory() as db:
        user = db.get(User, user_id)
        assert user.status == "PENDING"


def test_repeated_review_and_invalid_target(admin_env):
    client, session_factory = admin_env

    admin_id = seed_user(
        session_factory,
        "ADMIN001",
        "ADMIN",
        "ACTIVE",
    )

    user_id = seed_user(
        session_factory,
        "G051",
        "USER",
        "PENDING",
    )

    assert login(client, "ADMIN001").status_code == 200

    headers = {
        "X-CSRF-Token": get_csrf(client),
    }

    approve_url = f"/api/admin/users/{user_id}/approve"
    reject_url = f"/api/admin/users/{user_id}/reject"

    assert client.post(
        approve_url,
        headers=headers,
    ).status_code == 200

    # 중복 승인 금지
    assert client.post(
        approve_url,
        headers=headers,
    ).status_code == 409

    # 승인 완료 후 반려 금지
    assert client.post(
        reject_url,
        headers=headers,
    ).status_code == 409

    # 존재하지 않는 사용자
    assert client.post(
        "/api/admin/users/999999/approve",
        headers=headers,
    ).status_code == 404

    # 관리자 계정은 승인 대상이 아님
    assert client.post(
        f"/api/admin/users/{admin_id}/approve",
        headers=headers,
    ).status_code == 409
