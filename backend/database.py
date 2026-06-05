import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "movies.db"

def get_db():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()