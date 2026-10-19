from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.auth import RegisterRequest, RegisterResponse
from app.security.passwords import hash_password


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


DUPLICATE_ID_MESSAGE = "이미 등록된 SKALA 고유번호입니다."


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RegisterResponse:

    normalized_id = payload.skala_id.casefold()

    existing_user_id = db.scalar(
        select(User.id).where(
            User.skala_id_key == normalized_id
        )
    )

    if existing_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_ID_MESSAGE,
        )

    user = User(
        skala_id=payload.skala_id,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )

    db.add(user)

    try:
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        # 동시 가입 요청으로 인한 고유번호 중복도 처리
        existing_user_id = db.scalar(
            select(User.id).where(
                User.skala_id_key == normalized_id
            )
        )

        if existing_user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DUPLICATE_ID_MESSAGE,
            ) from exc

        # 고유번호 중복 이외의 DB 오류는 숨기지 않음
        raise

    db.refresh(user)

    return RegisterResponse(
        id=user.id,
        skala_id=user.skala_id,
        name=user.name,
        status=user.status,
    )
