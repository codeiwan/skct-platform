from sqlalchemy import text

from app.db import create_db_engine


def test_sqlite_connection(tmp_path):
    database_file = tmp_path / "test.db"

    test_engine = create_db_engine(
        f"sqlite:///{database_file}"
    )

    try:
        with test_engine.connect() as connection:
            result = connection.execute(
                text("SELECT 1")
            )

            assert result.scalar_one() == 1
    finally:
        test_engine.dispose()


def test_sqlite_configuration(tmp_path):
    database_file = tmp_path / "test.db"

    test_engine = create_db_engine(
        f"sqlite:///{database_file}"
    )

    try:
        with test_engine.connect() as connection:
            foreign_keys = connection.exec_driver_sql(
                "PRAGMA foreign_keys"
            ).scalar_one()

            journal_mode = connection.exec_driver_sql(
                "PRAGMA journal_mode"
            ).scalar_one()

            assert foreign_keys == 1
            assert journal_mode.lower() == "wal"
    finally:
        test_engine.dispose()
