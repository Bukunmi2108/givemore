import sqlite3
from pathlib import Path
from typing import Any, Iterable

from fastapi import Request

DB_PATH = Path(__file__).resolve().parent / "movies.db"


def connect_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query_database(
    conn: sqlite3.Connection,
    query: str,
    params: Iterable[Any] = (),
) -> list[dict[str, Any]]:
    rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def load_db(app: Any) -> sqlite3.Connection:
    conn = connect_db()
    query_database(conn, "SELECT 1")
    app.state.db = conn
    return conn


def close_db(app: Any) -> None:
    conn = getattr(app.state, "db", None)
    if conn is not None:
        conn.close()
        app.state.db = None


def get_db(request: Request) -> sqlite3.Connection:
    return request.app.state.db
