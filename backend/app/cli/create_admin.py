import getpass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import User
from app.security.passwords import hash_password


def main() -> int:
    print("\n=== SKCT Platform 관리자 계정 생성 ===\n")

    skala_id = input("관리자 고유번호: ").strip()
    name = input("관리자 이름: ").strip()

    password = getpass.getpass("비밀번호: ")
    confirmation = getpass.getpass("비밀번호 확인: ")

    if password != confirmation:
        print("오류: 비밀번호가 일치하지 않습니다.")
        return 1

    if not 8 <= len(password) <= 128 or password.isspace():
        print("오류: 비밀번호는 8~128자로 입력해야 합니다.")
        return 1

    try:
        admin = User(
            skala_id=skala_id,
            name=name,
            password_hash=hash_password(password),
            role="ADMIN",
            status="ACTIVE",
        )
    except ValueError as exc:
        print(f"오류: {exc}")
        return 1

    with SessionLocal() as db:
        existing_id = db.scalar(
            select(User.id).where(
                User.skala_id_key == admin.skala_id_key
            )
        )

        if existing_id is not None:
            print("오류: 이미 등록된 고유번호입니다.")
            return 1

        db.add(admin)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            print("오류: 계정을 생성하지 못했습니다.")
            return 1

    print(f"\n관리자 계정 생성 완료: {admin.skala_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
