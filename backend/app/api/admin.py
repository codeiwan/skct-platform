from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.admin import (
    PendingUserResponse,
    ReviewUserResponse,
)
from app.security.permissions import require_admin
from app.security.sessions import require_csrf


router = APIRouter(
    prefix="/api/admin",
    tags=["Administration"],
)


@router.get(
    "/users/pending",
    response_model=list[PendingUserResponse],
)
def list_pending_users(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> list[PendingUserResponse]:

    users = db.scalars(
        select(User)
        .where(
            User.role == "USER",
            User.status == "PENDING",
        )
        .order_by(User.created_at, User.id)
    ).all()

    return [
        PendingUserResponse(
            id=user.id,
            skala_id=user.skala_id,
            name=user.name,
            created_at=user.created_at,
        )
        for user in users
    ]


def change_user_status(
    db: Session,
    user_id: int,
    new_status: Literal["ACTIVE", "REJECTED"],
) -> ReviewUserResponse:

    # PENDING 상태인 일반 사용자만 변경
    result = db.execute(
        update(User)
        .where(
            User.id == user_id,
            User.role == "USER",
            User.status == "PENDING",
        )
        .values(status=new_status)
    )

    if result.rowcount != 1:
        db.rollback()

        user = db.get(User, user_id)

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="사용자를 찾을 수 없습니다.",
            )

        raise HTTPException(
            status_code=409,
            detail="승인 대기 상태인 일반 사용자만 처리할 수 있습니다.",
        )

    db.commit()

    user = db.get(User, user_id)

    return ReviewUserResponse(
        id=user.id,
        skala_id=user.skala_id,
        name=user.name,
        status=user.status,
    )


@router.post(
    "/users/{user_id}/approve",
    response_model=ReviewUserResponse,
    dependencies=[Depends(require_csrf)],
)
def approve_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> ReviewUserResponse:

    return change_user_status(
        db=db,
        user_id=user_id,
        new_status="ACTIVE",
    )


@router.post(
    "/users/{user_id}/reject",
    response_model=ReviewUserResponse,
    dependencies=[Depends(require_csrf)],
)
def reject_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> ReviewUserResponse:

    return change_user_status(
        db=db,
        user_id=user_id,
        new_status="REJECTED",
    )
