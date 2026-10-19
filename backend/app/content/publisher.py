import argparse
import sys

from pathlib import Path

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.content.importer import STORAGE_ROOT
from app.content.readiness import check_exam_readiness
from app.db import SessionLocal
from app.models import Exam


class PublicationError(Exception):
    pass


def publish_exam(
    code: str,
    *,
    content_reviewed: bool,
    session_factory: sessionmaker[Session] = SessionLocal,
    storage_root: Path = STORAGE_ROOT,
) -> None:

    if not content_reviewed:
        raise PublicationError(
            "실제 문제 내용과 정답에 대한 관리자 검토가 필요합니다."
        )

    if code.startswith("demo-"):
        raise PublicationError(
            "데모 시험은 공개할 수 없습니다."
        )

    readiness = check_exam_readiness(
        code,
        session_factory=session_factory,
        storage_root=storage_root,
    )

    if not readiness.ready:
        raise PublicationError(
            "공개 준비 검증 실패:\n"
            + "\n".join(readiness.errors)
        )

    # DRAFT -> PUBLISHED 전환
    # 다른 상태의 시험은 업데이트하지 않음
    with session_factory.begin() as db:
        result = db.execute(
            update(Exam)
            .where(
                Exam.code == code,
                Exam.status == "DRAFT",
            )
            .values(status="PUBLISHED")
        )

        if result.rowcount != 1:
            raise PublicationError(
                "시험 상태가 변경되었거나 공개 가능한 시험이 아닙니다."
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SKCT 시험 콘텐츠 공개"
    )

    parser.add_argument(
        "exam_code",
        help="공개할 시험 코드",
    )

    parser.add_argument(
        "--confirm-reviewed",
        action="store_true",
        help="실제 문제와 정답을 직접 검토했음을 확인",
    )

    args = parser.parse_args()

    try:
        publish_exam(
            args.exam_code,
            content_reviewed=args.confirm_reviewed,
        )

    except (
        PublicationError,
        SQLAlchemyError,
        OSError,
    ) as exc:
        print(f"[FAIL] 시험 공개 실패: {exc}")
        return 1

    print(f"[PASS] 시험 공개 완료: {args.exam_code}")
    print("시험 상태: PUBLISHED")

    return 0


if __name__ == "__main__":
    sys.exit(main())
