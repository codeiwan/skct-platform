import argparse
import csv
import sys

from pathlib import Path

import yaml

from pypdf import PdfWriter

from app.content.validator import SECTION_TYPES


def create_demo_exam(folder: Path) -> None:
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError(
            f"디렉터리에 이미 파일이 존재합니다: {folder}"
        )

    folder.mkdir(parents=True, exist_ok=True)

    sections = []

    for index, section_type in enumerate(
        SECTION_TYPES,
        start=1,
    ):
        sections.append(
            {
                "section_number": index,
                "section_type": section_type,
                "start_page": 2 + (index - 1) * 8,
                "question_count": 20,
                "duration_seconds": 900,
            }
        )

    manifest = {
        "code": "demo-exam-01",
        "book_title": "DEMO SKCT 문제집",
        "publisher": "테스트 전용",
        "title": "DEMO 실전 모의고사 1회",
        "content_version": 1,
        "pdf_filename": "questions.pdf",
        "sections": sections,
    }

    with (folder / "exam.yaml").open(
        "w",
        encoding="utf-8",
    ) as file:
        yaml.safe_dump(
            manifest,
            file,
            allow_unicode=True,
            sort_keys=False,
        )

    with (folder / "answers.csv").open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["section", "question", "answer"],
        )

        writer.writeheader()

        for section_type in SECTION_TYPES:
            for question in range(1, 21):
                writer.writerow(
                    {
                        "section": section_type,
                        "question": question,
                        "answer": (question - 1) % 5 + 1,
                    }
                )

    # 테스트 전용 빈 PDF: 실제 문제는 포함하지 않음
    pdf = PdfWriter()

    for _ in range(40):
        pdf.add_blank_page(
            width=595,
            height=842,
        )

    pdf.write(str(folder / "questions.pdf"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SKCT 데모 시험 생성"
    )

    parser.add_argument(
        "output_dir",
        type=Path,
    )

    args = parser.parse_args()

    try:
        create_demo_exam(args.output_dir)
    except (OSError, FileExistsError) as exc:
        print(f"[FAIL] {exc}")
        return 1

    print(f"[PASS] 데모 시험 생성: {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
