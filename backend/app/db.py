import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# 프로젝트 최상위 디렉터리
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 데이터베이스 저장 위치
DB_PATH = Path(
    os.environ.get(
        "SKCT_DB_PATH",
        str(PROJECT_ROOT / "storage" / "skct.db"),
    )
).expanduser().resolve()

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"


class Base(DeclarativeBase):
    pass


def create_db_engine(database_url: str = DATABASE_URL) -> Engine:
    engine = create_engine(
        database_url,
        connect_args={"timeout": 10},
    )

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()

            try:
                cursor.execute("PRAGMA foreign_keys=ON")

                if engine.url.database != ":memory:":
                    cursor.execute("PRAGMA journal_mode=WAL")
            finally:
                cursor.close()

    return engine


engine = create_db_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)
