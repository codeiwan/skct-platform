import argparse
import csv
import sys

from dataclasses import dataclass
from pathlib import Path

import yaml

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.content.importer import (
    STORAGE_ROOT,
    package_path,
    verify_exam_pdf,
)
from app.content.validator import (
    SECTION_TYPES,
    ExamSpec,
    validate_exam_dir,
)
from app.db import SessionLocal
from app.models import (
    Exam,
    ExamBook,
    ExamSection,
    ExamAnswerKey,
)


@dataclass(frozen=True)
class ReadinessResult:
    code: str
    errors: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return len(self.errors) == 0


def check_exam_readiness(
    code: str,
    *,
    session_factory: sessionmaker[Session] = SessionLocal,
    storage_root: Path = STORAGE_ROOT,
) -> ReadinessResult:

    errors: list[str] = []

    with session_factory() as db:
        exam = db.scalar(
            select(Exam).where(Exam.code == code)
        )

        if exam is None:
            return ReadinessResult(
                code=code,
                errors=("등록된 시험을 찾을 수 없습니다.",),
            )

        # 1. 시험 상태 확인
        if exam.status != "DRAFT":
            errors.append(
                "공개 준비 검사는 DRAFT 시험만 대상으로 합니다."
            )

        # 2. 시험 유형 확인
        sections = db.scalars(
            select(ExamSection)
            .where(ExamSection.exam_id == exam.id)
            .order_by(ExamSection.section_number)
        ).all()

        if len(sections) != 5:
            errors.append(
                f"유형은 5개여야 합니다. 현재 {len(sections)}개입니다."
            )

        section_numbers = [
            section.section_number for section in sections
        ]

        if section_numbers != [1, 2, 3, 4, 5]:
            errors.append("시험 유형 순서가 올바르지 않습니다.")

        section_types = [
            section.section_type for section in sections
        ]

        if section_types != list(SECTION_TYPES):
            errors.append("시험 유형 구성이 올바르지 않습니다.")

        pages = [
            section.start_page for section in sections
        ]

        if any(page < 1 for page in pages):
            errors.append("PDF 시작 페이지가 올바르지 않습니다.")

        if any(
            current >= following
            for current, following in zip(pages, pages[1:])
        ):
            errors.append(
                "PDF 시작 페이지는 순서대로 증가해야 합니다."
            )

        for section in sections:
            if section.question_count != 20:
                errors.append(
                    f"{section.section_type}: 문항 수가 20개가 아닙니다."
                )

            if section.duration_seconds != 900:
                errors.append(
                    f"{section.section_type}: 제한시간이 900초가 아닙니다."
                )

        # 3. DB 정답 검증
        answers = db.scalars(
            select(ExamAnswerKey)
            .join(
                ExamSection,
                ExamAnswerKey.section_id == ExamSection.id,
            )
            .where(ExamSection.exam_id == exam.id)
        ).all()

        if len(answers) != 100:
            errors.append(
                f"정답은 100개여야 합니다. 현재 {len(answers)}개입니다."
            )

        section_by_id = {
            section.id: section for section in sections
        }

        for section in sections:
            section_answers = [
                answer
                for answer in answers
                if answer.section_id == section.id
            ]

            numbers = [
                answer.question_number
                for answer in section_answers
            ]

            if (
                len(section_answers) != 20
                or set(numbers) != set(range(1, 21))
            ):
                errors.append(
                    f"{section.section_type}: "
                    "1~20번 정답이 완전하지 않습니다."
                )

            if any(
                not 1 <= answer.correct_option <= 5
                for answer in section_answers
            ):
                errors.append(
                    f"{section.section_type}: 정답 범위가 잘못되었습니다."
                )

        # 4. 서버에 보관된 콘텐츠 검증
        pdf_path = package_path(exam, storage_root)
        package_dir = pdf_path.parent

        package_errors = validate_exam_dir(package_dir)

        for error in package_errors:
            errors.append(f"보관 콘텐츠 오류: {error}")

        # 5. PDF SHA-256 검증
        try:
            if not verify_exam_pdf(exam, storage_root):
                errors.append(
                    "PDF 파일이 없거나 SHA-256이 일치하지 않습니다."
                )
        except OSError as exc:
            errors.append(f"PDF 무결성 검사 실패: {exc}")

        # 6. DB와 등록 당시 콘텐츠 비교
        if not package_errors:
            try:
                manifest = yaml.safe_load(
                    (package_dir / "exam.yaml").read_text(
                        encoding="utf-8"
                    )
                )

                spec = ExamSpec.model_validate(manifest)

                book = db.get(ExamBook, exam.book_id)

                if (
                    spec.code != exam.code
                    or spec.title != exam.title
                    or spec.content_version != exam.content_version
                    or spec.pdf_filename != exam.pdf_filename
                ):
                    errors.append(
                        "시험 기본정보가 보관된 YAML과 다릅니다."
                    )

                if (
                    book is None
                    or spec.book_title != book.title
                    or spec.publisher != book.publisher
                ):
                    errors.append(
                        "문제집 정보가 보관된 YAML과 다릅니다."
                    )

                db_sections = [
                    (
                        section.section_number,
                        section.section_type,
                        section.start_page,
                        section.question_count,
                        section.duration_seconds,
                    )
                    for section in sections
                ]

                file_sections = [
                    (
                        section.section_number,
                        section.section_type,
                        section.start_page,
                        section.question_count,
                        section.duration_seconds,
                    )
                    for section in spec.sections
                ]

                if db_sections != file_sections:
                    errors.append(
                        "유형 정보가 보관된 YAML과 다릅니다."
                    )

                with (package_dir / "answers.csv").open(
                    encoding="utf-8-sig",
                    newline="",
                ) as file:
                    csv_rows = list(csv.DictReader(file))

                file_answers = {
                    (row["section"], int(row["question"])):
                    int(row["answer"])
                    for row in csv_rows
                }

                db_answers = {
                    (
                        section_by_id[answer.section_id].section_type,
                        answer.question_number,
                    ): answer.correct_option
                    for answer in answers
                    if answer.section_id in section_by_id
                }

                if file_answers != db_answers:
                    errors.append(
                        "DB 정답과 보관된 CSV 정답이 일치하지 않습니다."
                    )

            except (OSError, ValueError, yaml.YAMLError, csv.Error) as exc:
                errors.append(
                    f"보관 콘텐츠와 DB 비교 실패: {exc}"
                )

    return ReadinessResult(
        code=code,
        errors=tuple(errors),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SKCT 시험 공개 준비 상태 검증"
    )

    parser.add_argument(
        "exam_code",
        help="검증할 시험 코드",
    )

    args = parser.parse_args()

    result = check_exam_readiness(args.exam_code)

    if not result.ready:
        print(f"[FAIL] 시험 공개 준비 검증: {result.code}")

        for error in result.errors:
            print(f" - {error}")

        return 1

    print(f"[PASS] 시험 공개 준비 검증: {result.code}")
    print("[PASS] 5개 유형 / 100개 정답")
    print("[PASS] DB와 등록 콘텐츠 일치")
    print("[PASS] PDF 무결성 확인")
    print("현재 상태: DRAFT (공개되지 않음)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
