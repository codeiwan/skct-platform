from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuthSession, User
from app.security.sessions import get_current_session


def require_admin(
    auth_session: Annotated[
        AuthSession,
        Depends(get_current_session),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User:

    user = db.get(User, auth_session.user_id)

    if user is None or user.role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="관리자 권한이 필요합니다.",
        )

    return user
