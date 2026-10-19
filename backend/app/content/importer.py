import argparse
import csv
import hashlib
import shutil
import sys
import tempfile

from dataclasses import dataclass
from pathlib import Path

import yaml

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.content.validator import (
    ExamSpec,
    validate_exam_dir,
)
from app.db import PROJECT_ROOT, SessionLocal
from app.models import (
    Exam,
    ExamBook,
    ExamSection,
    ExamAnswerKey,
)


STORAGE_ROOT = PROJECT_ROOT / "storage" / "exam_packages"

PACKAGE_FILES = (
    "exam.yaml",
    "answers.csv",
    "questions.pdf",
)


class ContentImportError(Exception):
    pass


@dataclass(frozen=True)
class ImportResult:
    exam_id: int
    code: str
    section_count: int
    answer_count: int
    pdf_sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def package_path(
    exam: Exam,
    storage_root: Path = STORAGE_ROOT,
) -> Path:
    return (
        storage_root
        / exam.code
        / f"v{exam.content_version}"
        / "questions.pdf"
    )


def verify_exam_pdf(
    exam: Exam,
    storage_root: Path = STORAGE_ROOT,
) -> bool:
    if (
        exam.pdf_filename != "questions.pdf"
        or not exam.pdf_sha256
    ):
        return False

    path = package_path(exam, storage_root)

    if not path.is_file():
        return False

    return sha256_file(path) == exam.pdf_sha256


def import_exam(
    source_dir: Path,
    *,
    session_factory: sessionmaker[Session] = SessionLocal,
    storage_root: Path = STORAGE_ROOT,
) -> ImportResult:

    source_dir = source_dir.resolve()
    storage_root = storage_root.resolve()

    # 1. 기존 검증기로 원본 확인
    errors = validate_exam_dir(source_dir)

    if errors:
        raise ContentImportError(
            "콘텐츠 검증 실패:\n" + "\n".join(errors)
        )

    storage_root.mkdir(parents=True, exist_ok=True)

    # 2. 임시 디렉터리에 콘텐츠 전체 복사
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=".staging-",
            dir=storage_root,
        )
    )

    promoted = False
    target_dir: Path | None = None

    try:
        for filename in PACKAGE_FILES:
            shutil.copy2(
                source_dir / filename,
                staging_dir / filename,
            )

        # 3. 실제 등록할 복사본을 다시 검증
        errors = validate_exam_dir(staging_dir)

        if errors:
            raise ContentImportError(
                "복사된 콘텐츠 검증 실패:\n"
                + "\n".join(errors)
            )

        manifest_data = yaml.safe_load(
            (staging_dir / "exam.yaml").read_text(
                encoding="utf-8"
            )
        )

        spec = ExamSpec.model_validate(manifest_data)

        with (staging_dir / "answers.csv").open(
            encoding="utf-8-sig",
            newline="",
        ) as file:
            answers = list(csv.DictReader(file))

        pdf_hash = sha256_file(
            staging_dir / "questions.pdf"
        )

        target_dir = (
            storage_root
            / spec.code
            / f"v{spec.content_version}"
        )

        # 4. DB 트랜잭션 시작
        with session_factory.begin() as db:

            existing_exam = db.scalar(
                select(Exam.id).where(
                    Exam.code == spec.code
                )
            )

            if existing_exam is not None:
                raise ContentImportError(
                    f"이미 등록된 시험 코드입니다: {spec.code}"
                )

            if target_dir.exists():
                raise ContentImportError(
                    f"보관 경로가 이미 존재합니다: {target_dir}"
                )

            # 5. 문제집 조회 또는 생성
            book = db.scalar(
                select(ExamBook)
                .where(
                    ExamBook.title == spec.book_title,
                    ExamBook.publisher == spec.publisher,
                )
                .order_by(ExamBook.id)
            )

            if book is None:
                book = ExamBook(
                    title=spec.book_title,
                    publisher=spec.publisher,
                )

                db.add(book)
                db.flush()

            # 6. 시험 등록: 반드시 DRAFT
            exam = Exam(
                book_id=book.id,
                code=spec.code,
                title=spec.title,
                status="DRAFT",
                content_version=spec.content_version,
                pdf_filename=spec.pdf_filename,
                pdf_sha256=pdf_hash,
            )

            db.add(exam)
            db.flush()

            # 7. 유형 등록
            section_ids: dict[str, int] = {}

            for section_spec in spec.sections:
                section = ExamSection(
                    exam_id=exam.id,
                    section_number=section_spec.section_number,
                    section_type=section_spec.section_type,
                    start_page=section_spec.start_page,
                    question_count=section_spec.question_count,
                    duration_seconds=section_spec.duration_seconds,
                )

                db.add(section)
                db.flush()

                section_ids[section_spec.section_type] = section.id

            # 8. 정답 100개 등록
            for answer in answers:
                db.add(
                    ExamAnswerKey(
                        section_id=section_ids[answer["section"]],
                        question_number=int(answer["question"]),
                        correct_option=int(answer["answer"]),
                    )
                )

            db.flush()

            # 9. 검증된 패키지를 서버 보관 위치로 이동
            target_dir.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            staging_dir.rename(target_dir)
            promoted = True

            result = ImportResult(
                exam_id=exam.id,
                code=exam.code,
                section_count=len(spec.sections),
                answer_count=len(answers),
                pdf_sha256=pdf_hash,
            )

        # 트랜잭션 블록을 정상 종료해야 DB가 COMMIT됨
        return result

    except Exception:
        # DB 오류 시 트랜잭션은 롤백되며,
        # 이번 작업에서 이동한 파일도 정리
        if promoted and target_dir is not None:
            shutil.rmtree(target_dir)

        raise

    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SKCT 공식 시험 콘텐츠 등록"
    )

    parser.add_argument(
        "exam_dir",
        type=Path,
        help="시험 콘텐츠 원본 디렉터리",
    )

    args = parser.parse_args()

    try:
        result = import_exam(args.exam_dir)

    except (ContentImportError, OSError, SQLAlchemyError) as exc:
        print(f"[FAIL] 시험 등록 실패: {exc}")
        return 1

    print("[PASS] 시험 콘텐츠 등록 완료")
    print(f"시험 ID: {result.exam_id}")
    print(f"시험 코드: {result.code}")
    print(f"유형: {result.section_count}개")
    print(f"정답: {result.answer_count}개")
    print(f"PDF SHA-256: {result.pdf_sha256}")
    print("시험 상태: DRAFT")

    return 0


if __name__ == "__main__":
    sys.exit(main())
