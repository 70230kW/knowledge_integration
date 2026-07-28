import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _connect() -> sqlite3.Connection:
    # FastAPIの同期依存関係はスレッドプール内で実行され、yield前後で
    # 別スレッドに切り替わることがあるためcheck_same_thread=Falseが必要。
    # 1リクエスト内で同時並行アクセスはしないため安全。
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_connection():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
