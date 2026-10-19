import hashlib
import os
import secrets

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import (
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuthSession, User


SESSION_DURATION = timedelta(days=30)
RENEWAL_THRESHOLD = timedelta(days=7)

APP_ENV = os.getenv("SKCT_ENV", "development")

if APP_ENV not in {"development", "production"}:
    raise RuntimeError("SKCT_ENV must be development or production")

IS_PRODUCTION = APP_ENV == "production"

COOKIE_NAME = (
    "__Host-skct_session"
    if IS_PRODUCTION
    else "skct_session"
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def set_session_cookie(
    response: Response,
    token: str,
) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=int(SESSION_DURATION.total_seconds()),
        path="/",
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
    )


def get_current_session(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> AuthSession:

    token = request.cookies.get(COOKIE_NAME)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="로그인이 필요합니다.",
        )

    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_token(token)
        )
    )

    now = utc_now()

    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
    ):
        raise HTTPException(
            status_code=401,
            detail="유효하지 않거나 만료된 세션입니다.",
        )

    user = db.get(User, session.user_id)

    if user is None or user.status != "ACTIVE":
        raise HTTPException(
            status_code=401,
            detail="활성화되지 않은 계정입니다.",
        )

    # 만료가 가까워진 세션만 연장
    if session.expires_at - now <= RENEWAL_THRESHOLD:
        session.expires_at = now + SESSION_DURATION

        db.commit()

        set_session_cookie(response, token)

    return session


def require_csrf(
    session: Annotated[
        AuthSession,
        Depends(get_current_session),
    ],
    supplied_token: Annotated[
        str | None,
        Header(alias="X-CSRF-Token"),
    ] = None,
) -> None:

    if not supplied_token or not secrets.compare_digest(
        supplied_token,
        session.csrf_token,
    ):
        raise HTTPException(
            status_code=403,
            detail="CSRF 검증에 실패했습니다.",
        )
