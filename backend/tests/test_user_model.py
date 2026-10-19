import pytest

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base, create_db_engine
from app.models import User


@pytest.fixture
def db_session(tmp_path):
    database_file = tmp_path / "users.db"

    engine = create_db_engine(
        f"sqlite:///{database_file}"
    )

    Base.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def make_user(skala_id: str) -> User:
    return User(
        skala_id=skala_id,
        name="테스트 사용자",
        password_hash="TEST_ONLY_NOT_A_REAL_PASSWORD_HASH",
    )


def test_create_user(db_session):
    user = make_user(" G051 ")

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.skala_id == "G051"
    assert user.skala_id_key == "g051"
    assert user.role == "USER"
    assert user.status == "PENDING"
    assert user.created_at is not None


def test_duplicate_skala_id(db_session):
    first = make_user("G051")
    second = make_user("g051")

    db_session.add(first)
    db_session.commit()

    db_session.add(second)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_custom_skala_id_format(db_session):
    user = make_user("SKALA-2026-XYZ")

    db_session.add(user)
    db_session.commit()

    assert user.skala_id == "SKALA-2026-XYZ"
    assert user.skala_id_key == "skala-2026-xyz"


def test_empty_skala_id():
    with pytest.raises(ValueError):
        make_user("   ")


def test_invalid_status(db_session):
    user = make_user("G052")
    user.status = "APPROVED"

    db_session.add(user)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
