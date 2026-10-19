from datetime import timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuthSession, User
from app.schemas.auth import (
    CsrfResponse,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
)
from app.security.passwords import (
    hash_password,
    verify_password,
)
from app.security.sessions import (
    COOKIE_NAME,
    SESSION_DURATION,
    clear_session_cookie,
    generate_token,
    get_current_session,
    hash_token,
    require_csrf,
    set_session_cookie,
    utc_now,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)

DUPLICATE_ID_MESSAGE = "이미 등록된 SKALA 고유번호입니다."


# --------------------------------------------------
# 회원가입: 기존 기능 유지
# --------------------------------------------------

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
            status_code=409,
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

        existing_user_id = db.scalar(
            select(User.id).where(
                User.skala_id_key == normalized_id
            )
        )

        if existing_user_id is not None:
            raise HTTPException(
                status_code=409,
                detail=DUPLICATE_ID_MESSAGE,
            ) from exc

        raise

    db.refresh(user)

    return RegisterResponse(
        id=user.id,
        skala_id=user.skala_id,
        name=user.name,
        status=user.status,
    )


# --------------------------------------------------
# 로그인
# --------------------------------------------------

@router.post(
    "/login",
    response_model=UserResponse,
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:

    normalized_id = payload.skala_id.casefold()

    user = db.scalar(
        select(User).where(
            User.skala_id_key == normalized_id
        )
    )

    if user is None or not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="고유번호 또는 비밀번호가 올바르지 않습니다.",
        )

    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=403,
            detail="활성화되지 않은 계정입니다. 관리자 승인을 확인하세요.",
        )

    now = utc_now()

    # 현재 브라우저의 기존 로그인 세션은 무효화
    previous_token = request.cookies.get(COOKIE_NAME)

    if previous_token:
        previous_session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == hash_token(previous_token)
            )
        )

        if previous_session is not None:
            previous_session.revoked_at = now

    # 새 세션은 반드시 새로운 랜덤 토큰으로 발급
    token = generate_token()
    csrf_token = generate_token()

    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_token(token),
            csrf_token=csrf_token,
            expires_at=now + SESSION_DURATION,
        )
    )

    db.commit()

    set_session_cookie(response, token)

    return UserResponse(
        id=user.id,
        skala_id=user.skala_id,
        name=user.name,
        role=user.role,
        status=user.status,
    )


# --------------------------------------------------
# 현재 로그인 사용자 확인
# --------------------------------------------------

@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    session: Annotated[
        AuthSession,
        Depends(get_current_session),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:

    user = db.get(User, session.user_id)

    return UserResponse(
        id=user.id,
        skala_id=user.skala_id,
        name=user.name,
        role=user.role,
        status=user.status,
    )


# --------------------------------------------------
# CSRF 토큰 조회
# --------------------------------------------------

@router.get(
    "/csrf",
    response_model=CsrfResponse,
)
def get_csrf(
    session: Annotated[
        AuthSession,
        Depends(get_current_session),
    ],
) -> CsrfResponse:

    return CsrfResponse(
        csrf_token=session.csrf_token,
    )


# --------------------------------------------------
# 로그아웃
# --------------------------------------------------

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def logout(
    response: Response,
    session: Annotated[
        AuthSession,
        Depends(get_current_session),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> None:

    session.revoked_at = utc_now()

    db.commit()

    clear_session_cookie(response)
