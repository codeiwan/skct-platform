import argparse
import csv
import sys

from pathlib import Path
from typing import Literal

import yaml

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)
from pypdf import PdfReader


SECTION_TYPES = (
    "언어이해",
    "자료해석",
    "창의수리",
    "언어추리",
    "수열추리",
)

CSV_COLUMNS = ["section", "question", "answer"]


class SectionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    section_number: int = Field(ge=1, le=5)
    section_type: str
    start_page: int = Field(ge=1)
    question_count: Literal[20]
    duration_seconds: Literal[900]


class ExamSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    code: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )

    book_title: str = Field(min_length=1, max_length=200)
    publisher: str | None = None
    title: str = Field(min_length=1, max_length=200)

    content_version: int = Field(ge=1)
    pdf_filename: Literal["questions.pdf"]

    sections: list[SectionSpec] = Field(
        min_length=5,
        max_length=5,
    )

    @model_validator(mode="after")
    def validate_sections(self):
        pages = []

        for index, section in enumerate(self.sections, start=1):
            expected_type = SECTION_TYPES[index - 1]

            if (
                section.section_number != index
                or section.section_type != expected_type
            ):
                raise ValueError(
                    f"{index}번 유형은 {expected_type}이어야 합니다."
                )

            pages.append(section.start_page)

        if any(
            current >= following
            for current, following in zip(pages, pages[1:])
        ):
            raise ValueError(
                "PDF 시작 페이지는 유형 순서대로 증가해야 합니다."
            )

        return self


def validate_exam_dir(folder: Path) -> list[str]:
    errors: list[str] = []

    if not folder.is_dir():
        return [f"시험 디렉터리가 없습니다: {folder}"]

    # 1. YAML 검증
    manifest_path = folder / "exam.yaml"

    exam: ExamSpec | None = None

    try:
        raw_data = yaml.safe_load(
            manifest_path.read_text(encoding="utf-8")
        )

        exam = ExamSpec.model_validate(raw_data)

    except (OSError, yaml.YAMLError, ValidationError) as exc:
        errors.append(f"exam.yaml 오류: {exc}")

    # 2. PDF 검증
    pdf_path = folder / "questions.pdf"

    if not pdf_path.is_file():
        errors.append("questions.pdf 파일이 없습니다.")
    else:
        try:
            reader = PdfReader(str(pdf_path))

            if reader.is_encrypted:
                errors.append(
                    "암호화된 PDF는 등록할 수 없습니다."
                )
            else:
                page_count = len(reader.pages)

                if page_count == 0:
                    errors.append("PDF 페이지가 없습니다.")

                if exam is not None:
                    for section in exam.sections:
                        if section.start_page > page_count:
                            errors.append(
                                f"{section.section_type}: "
                                f"시작 페이지 {section.start_page}가 "
                                f"전체 {page_count}페이지를 초과합니다."
                            )

        except Exception as exc:
            errors.append(
                f"PDF 파일을 읽을 수 없습니다: {exc}"
            )

    # 3. 정답 CSV 검증
    answers_path = folder / "answers.csv"

    if not answers_path.is_file():
        errors.append("answers.csv 파일이 없습니다.")
        return errors

    try:
        with answers_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            if reader.fieldnames != CSV_COLUMNS:
                errors.append(
                    "CSV 헤더는 section,question,answer이어야 합니다."
                )
                return errors

            rows = list(reader)

    except (OSError, UnicodeError, csv.Error) as exc:
        errors.append(f"answers.csv 오류: {exc}")
        return errors

    if len(rows) != 100:
        errors.append(
            f"정답은 100행이어야 합니다. 현재 {len(rows)}행입니다."
        )

    expected = {
        (section, str(question))
        for section in SECTION_TYPES
        for question in range(1, 21)
    }

    seen: set[tuple[str, str]] = set()

    for line_number, row in enumerate(rows, start=2):
        section = row.get("section")
        question = row.get("question")
        answer = row.get("answer")

        if section not in SECTION_TYPES:
            errors.append(
                f"CSV {line_number}행: 알 수 없는 유형입니다."
            )
            continue

        if question not in {
            str(number) for number in range(1, 21)
        }:
            errors.append(
                f"CSV {line_number}행: 문항번호는 1~20이어야 합니다."
            )
            continue

        if answer not in {"1", "2", "3", "4", "5"}:
            errors.append(
                f"CSV {line_number}행: 정답은 1~5이어야 합니다."
            )

        key = (section, question)

        if key in seen:
            errors.append(
                f"CSV {line_number}행: "
                f"{section} {question}번 정답이 중복되었습니다."
            )

        seen.add(key)

    missing = expected - seen

    if missing:
        errors.append(
            f"정답이 누락된 문항이 {len(missing)}개 있습니다."
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SKCT 시험 콘텐츠 검증"
    )

    parser.add_argument(
        "exam_dir",
        type=Path,
        help="시험 콘텐츠 디렉터리",
    )

    args = parser.parse_args()

    errors = validate_exam_dir(args.exam_dir)

    if errors:
        print("[FAIL] 시험 콘텐츠 검증 실패")

        for error in errors:
            print(f" - {error}")

        return 1

    print("[PASS] 시험 콘텐츠 검증 성공")
    print("5개 유형 / 100개 정답 / PDF 검사 완료")

    return 0


if __name__ == "__main__":
    sys.exit(main())
