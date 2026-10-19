import csv

import pytest
import yaml

from app.content.demo import create_demo_exam
from app.content.validator import validate_exam_dir


@pytest.fixture
def demo_dir(tmp_path):
    folder = tmp_path / "demo-exam-01"
    create_demo_exam(folder)
    return folder


def read_answers(folder):
    with (folder / "answers.csv").open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def write_answers(folder, rows):
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
        writer.writerows(rows)


def read_manifest(folder):
    with (folder / "exam.yaml").open(
        encoding="utf-8",
    ) as file:
        return yaml.safe_load(file)


def write_manifest(folder, data):
    with (folder / "exam.yaml").open(
        "w",
        encoding="utf-8",
    ) as file:
        yaml.safe_dump(
            data,
            file,
            allow_unicode=True,
            sort_keys=False,
        )


def test_valid_demo_content(demo_dir):
    assert validate_exam_dir(demo_dir) == []


def test_missing_answer(demo_dir):
    rows = read_answers(demo_dir)
    rows.pop()
    write_answers(demo_dir, rows)

    errors = validate_exam_dir(demo_dir)

    assert any("100행" in error for error in errors)
    assert any("누락" in error for error in errors)


def test_duplicate_answer(demo_dir):
    rows = read_answers(demo_dir)
    rows[1] = rows[0].copy()
    write_answers(demo_dir, rows)

    errors = validate_exam_dir(demo_dir)

    assert any("중복" in error for error in errors)


def test_invalid_answer_option(demo_dir):
    rows = read_answers(demo_dir)
    rows[0]["answer"] = "6"
    write_answers(demo_dir, rows)

    errors = validate_exam_dir(demo_dir)

    assert any("1~5" in error for error in errors)


def test_invalid_section_order(demo_dir):
    data = read_manifest(demo_dir)

    data["sections"][1]["section_type"] = "수열추리"

    write_manifest(demo_dir, data)

    errors = validate_exam_dir(demo_dir)

    assert any("유형" in error for error in errors)


def test_pdf_page_out_of_range(demo_dir):
    data = read_manifest(demo_dir)

    data["sections"][4]["start_page"] = 999

    write_manifest(demo_dir, data)

    errors = validate_exam_dir(demo_dir)

    assert any("초과" in error for error in errors)


def test_missing_pdf(demo_dir):
    (demo_dir / "questions.pdf").unlink()

    errors = validate_exam_dir(demo_dir)

    assert any("questions.pdf" in error for error in errors)
