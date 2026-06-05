"""Validate the generated movies.db artifact.

Ported from validate.ipynb -- standalone guard for the DB (plan §9.3), runnable
in CI (plan §14.2). Three design rules:

1. DB-self-contained: no CSVs, no pipeline recomputation, no heavy deps --
   stdlib only, so CI needs nothing installed.
2. Run ALL checks, report ALL failures -- a damage report, not assert-and-die.
3. The DB is opened READ-ONLY (mode=ro): validation can never mutate the artifact.

Usage:
    python validate_db.py [--db-path ../backend/movies.db]

Exit code 0 if every check passes, 1 otherwise.
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

EXPECTED = {
    "users": 610,
    "movies": 9742,
    "user_recs_per_user": 20,
    "user_rec_rows": 610 * 20,
    "movies_with_similarity": 9742 - 5,
    "popular_rows": 100,
    "rating_count": 100836,            # known dataset constant (cannot recount without CSVs)
    "min_db_bytes": 1_000_000,         # truncated-download guard
    "demo_users": [1, 57, 414, 610],   # frontend quick-pick IDs (plan §11.4)
    # the 5 known empty-vector films (min_df=2 dropped all their tokens; build.md Stage 8)
    "gap_movies": {129250, 155589, 156605, 169034, 171495},
}

TABLES = {"movies", "users", "popular_movies", "user_recommendations",
          "movie_similarity", "ratings_summary"}

INDEXES = {"idx_user_recommendations_user_id", "idx_movie_similarity_movie_id",
           "idx_movies_title", "idx_popular_movies_rank"}

SCHEMA = {
    "movies": {"movie_id", "title", "genres", "year"},
    "users": {"user_id", "rating_count", "avg_rating"},
    "popular_movies": {"rank", "movie_id", "score", "rating_count", "avg_rating"},
    "user_recommendations": {"user_id", "rank", "movie_id", "score"},
    "movie_similarity": {"movie_id", "rank", "similar_movie_id", "score"},
    "ratings_summary": {"key", "value"},
}

CHECKS = []


def check(name):
    """Register a validation check. fn(conn) -> (ok: bool, detail: str)."""
    def wrap(fn):
        CHECKS.append((name, fn))
        return fn
    return wrap


def scalar(conn, sql):
    return conn.execute(sql).fetchone()[0]


# --- A. Existence & structure (A1/A2 are file-level, run inside the runner) ---

@check("A3 all six tables exist")
def a3(conn):
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = TABLES - have
    return (not missing, f"missing: {sorted(missing)}" if missing else "")


@check("A4 all four indexes exist")
def a4(conn):
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    missing = INDEXES - have
    return (not missing, f"missing: {sorted(missing)}" if missing else "")


@check("A5 expected columns per table")
def a5(conn):
    bad = []
    for t, cols in SCHEMA.items():
        have = {r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')}
        if have != cols:
            bad.append(f"{t}: missing {sorted(cols - have)}, extra {sorted(have - cols)}")
    return (not bad, "; ".join(bad))


# --- B. Counts & coverage ---

@check("B1 movies count")
def b1(conn):
    n = scalar(conn, "SELECT COUNT(*) FROM movies")
    return (n == EXPECTED["movies"], f"{n}")


@check("B2 users count")
def b2(conn):
    n = scalar(conn, "SELECT COUNT(*) FROM users")
    return (n == EXPECTED["users"], f"{n}")


@check("B3 popular_movies count")
def b3(conn):
    n = scalar(conn, "SELECT COUNT(*) FROM popular_movies")
    return (n == EXPECTED["popular_rows"], f"{n}")


@check("B4 user_recommendations rows + full user coverage")
def b4(conn):
    rows = scalar(conn, "SELECT COUNT(*) FROM user_recommendations")
    users = scalar(conn, "SELECT COUNT(DISTINCT user_id) FROM user_recommendations")
    ok = rows == EXPECTED["user_rec_rows"] and users == EXPECTED["users"]
    return (ok, f"{rows} rows, {users} users")


@check("B5 movies with similarity rows (expected 5-gap)")
def b5(conn):
    n = scalar(conn, "SELECT COUNT(DISTINCT movie_id) FROM movie_similarity")
    gap = EXPECTED["movies"] - n
    return (n == EXPECTED["movies_with_similarity"], f"{n} (gap {gap})")


@check("B6 ratings_summary has 5 keys incl generated_at")
def b6(conn):
    keys = {r[0] for r in conn.execute("SELECT key FROM ratings_summary")}
    ok = len(keys) == 5 and "generated_at" in keys
    return (ok, ", ".join(sorted(keys)))


# --- C. Referential integrity (Q17, re-asserted on the artifact) ---
# The DDL declares FKs, but SQLite does NOT enforce them unless PRAGMA
# foreign_keys=ON was set at write time -- these checks are the real enforcement.

ORPHAN_CHECKS = [
    ("C1 user_recommendations.movie_id -> movies",
     "SELECT COUNT(*) FROM user_recommendations t LEFT JOIN movies m ON t.movie_id = m.movie_id WHERE m.movie_id IS NULL"),
    ("C2 movie_similarity.movie_id -> movies",
     "SELECT COUNT(*) FROM movie_similarity t LEFT JOIN movies m ON t.movie_id = m.movie_id WHERE m.movie_id IS NULL"),
    ("C3 movie_similarity.similar_movie_id -> movies",
     "SELECT COUNT(*) FROM movie_similarity t LEFT JOIN movies m ON t.similar_movie_id = m.movie_id WHERE m.movie_id IS NULL"),
    ("C4 popular_movies.movie_id -> movies",
     "SELECT COUNT(*) FROM popular_movies t LEFT JOIN movies m ON t.movie_id = m.movie_id WHERE m.movie_id IS NULL"),
    ("C5 user_recommendations.user_id -> users",
     "SELECT COUNT(*) FROM user_recommendations t LEFT JOIN users u ON t.user_id = u.user_id WHERE u.user_id IS NULL"),
]

for _name, _sql in ORPHAN_CHECKS:
    def _orphan(conn, sql=_sql):
        n = scalar(conn, sql)
        return (n == 0, f"{n} orphans" if n else "")
    check(_name)(_orphan)


# --- D. Ranking invariants ---
# Rank is the authoritative order (build.md Stage 8) -- validate rank, not score order.

@check("D1 no self-similarity")
def d1(conn):
    n = scalar(conn, "SELECT COUNT(*) FROM movie_similarity WHERE movie_id = similar_movie_id")
    return (n == 0, f"{n} rows" if n else "")


@check("D2 movie_similarity ranks contiguous 1..N per movie")
def d2(conn):
    n = scalar(conn, '''
        SELECT COUNT(*) FROM (
            SELECT movie_id FROM movie_similarity
            GROUP BY movie_id
            HAVING MIN("rank") != 1 OR MAX("rank") != COUNT(*) OR COUNT(DISTINCT "rank") != COUNT(*)
        )''')
    return (n == 0, f"{n} bad groups" if n else "")


@check("D3 user_recommendations: exactly 20, ranks contiguous, per user")
def d3(conn):
    n = scalar(conn, f'''
        SELECT COUNT(*) FROM (
            SELECT user_id FROM user_recommendations
            GROUP BY user_id
            HAVING COUNT(*) != {EXPECTED["user_recs_per_user"]}
                OR MIN("rank") != 1 OR MAX("rank") != COUNT(*)
                OR COUNT(DISTINCT "rank") != COUNT(*)
        )''')
    return (n == 0, f"{n} bad groups" if n else "")


@check("D4 popular_movies ranks are exactly 1..100")
def d4(conn):
    lo, hi, cnt, dst = conn.execute(
        'SELECT MIN("rank"), MAX("rank"), COUNT(*), COUNT(DISTINCT "rank") FROM popular_movies').fetchone()
    want = EXPECTED["popular_rows"]
    ok = (lo, hi, cnt, dst) == (1, want, want, want)
    return (ok, f"min {lo}, max {hi}, n {cnt}")


@check("D5 no duplicate targets within a list")
def d5(conn):
    a = scalar(conn, "SELECT COUNT(*) FROM (SELECT 1 FROM user_recommendations GROUP BY user_id, movie_id HAVING COUNT(*) > 1)")
    b = scalar(conn, "SELECT COUNT(*) FROM (SELECT 1 FROM movie_similarity GROUP BY movie_id, similar_movie_id HAVING COUNT(*) > 1)")
    return (a == 0 and b == 0, f"recs {a}, sims {b}" if a or b else "")


# --- E. Value sanity ---

@check("E1 no NULL scores anywhere")
def e1(conn):
    n = sum(scalar(conn, f"SELECT COUNT(*) FROM {t} WHERE score IS NULL")
            for t in ("popular_movies", "user_recommendations", "movie_similarity"))
    return (n == 0, f"{n} NULLs" if n else "")


@check("E2 popular_movies values plausible")
def e2(conn):
    n = scalar(conn, '''
        SELECT COUNT(*) FROM popular_movies
        WHERE score NOT BETWEEN 0.5 AND 5.0
           OR avg_rating NOT BETWEEN 0.5 AND 5.0
           OR rating_count < 1''')
    return (n == 0, f"{n} bad rows" if n else "")


@check("E3 users values plausible")
def e3(conn):
    n = scalar(conn, '''
        SELECT COUNT(*) FROM users
        WHERE rating_count < 20 OR avg_rating NOT BETWEEN 0.5 AND 5.0''')
    return (n == 0, f"{n} bad rows" if n else "")


@check("E4 movies sane (title/genres non-empty, year NULL or 1900-2030)")
def e4(conn):
    n = scalar(conn, """
        SELECT COUNT(*) FROM movies
        WHERE title IS NULL OR TRIM(title) = ''
           OR genres IS NULL OR TRIM(genres) = ''
           OR (year IS NOT NULL AND year NOT BETWEEN 1900 AND 2030)""")
    return (n == 0, f"{n} bad rows" if n else "")


@check("E5 similarity scores within [0, 1] (float tolerance)")
def e5(conn):
    # cosine of identical TF-IDF vectors lands at 1 + ~4e-16 (machine epsilon);
    # validate the math property, not float noise -> tolerance 1e-9
    n = scalar(conn, "SELECT COUNT(*) FROM movie_similarity WHERE score < -1e-9 OR score > 1.000000001")
    return (n == 0, f"{n} out of range" if n else "")


# --- F. API-contract checks (phrased as the backend will query) ---

@check("F1 demo users (1, 57, 414, 610) each have exactly 20 recs")
def f1(conn):
    ids = ",".join(map(str, EXPECTED["demo_users"]))
    n = scalar(conn, f'''
        SELECT COUNT(*) FROM (
            SELECT user_id FROM user_recommendations
            WHERE user_id IN ({ids})
            GROUP BY user_id HAVING COUNT(*) = {EXPECTED["user_recs_per_user"]}
        )''')
    want = len(EXPECTED["demo_users"])
    return (n == want, f"{n}/{want} demo users ok")


@check("F2 unknown user 9999 -> no recs, popular fallback servable")
def f2(conn):
    unknown = scalar(conn, "SELECT COUNT(*) FROM user_recommendations WHERE user_id = 9999")
    pop = scalar(conn, "SELECT COUNT(*) FROM popular_movies")
    return (unknown == 0 and pop > 0, f"unknown rows {unknown}, popular {pop}")


@check("F3 title search servable ('matrix')")
def f3(conn):
    n = scalar(conn, "SELECT COUNT(*) FROM movies WHERE title LIKE '%matrix%'")
    return (n >= 1, f"{n} matches")


@check("F4 similar-movies path: hub full, known gaps empty")
def f4(conn):
    toy = scalar(conn, "SELECT COUNT(*) FROM movie_similarity WHERE movie_id = 1")
    gaps = {r[0] for r in conn.execute(
        "SELECT movie_id FROM movies WHERE movie_id NOT IN (SELECT DISTINCT movie_id FROM movie_similarity)")}
    ok = toy == 15 and gaps == EXPECTED["gap_movies"]
    return (ok, f"toy story {toy} rows; gaps {sorted(gaps)}")


# --- G. Summary consistency (the DB describing itself truthfully) ---

@check("G1 summary movie_count matches movies table")
def g1(conn):
    s = scalar(conn, "SELECT CAST(value AS INTEGER) FROM ratings_summary WHERE key = 'movie_count'")
    n = scalar(conn, "SELECT COUNT(*) FROM movies")
    return (s == n, f"summary {s} vs actual {n}")


@check("G2 summary user_count matches users table")
def g2(conn):
    s = scalar(conn, "SELECT CAST(value AS INTEGER) FROM ratings_summary WHERE key = 'user_count'")
    n = scalar(conn, "SELECT COUNT(*) FROM users")
    return (s == n, f"summary {s} vs actual {n}")


@check("G3 summary rating_count is the known dataset constant")
def g3(conn):
    s = scalar(conn, "SELECT CAST(value AS INTEGER) FROM ratings_summary WHERE key = 'rating_count'")
    return (s == EXPECTED["rating_count"], f"{s}")


@check("G4 generated_at parses as ISO-8601")
def g4(conn):
    v = scalar(conn, "SELECT value FROM ratings_summary WHERE key = 'generated_at'")
    try:
        datetime.fromisoformat(v)
        return (True, v)
    except (TypeError, ValueError):
        return (False, repr(v))


def run(db_path):
    """Run every check against db_path. Reports all results; returns overall verdict."""
    results = []

    # A1/A2: file-level pre-flight (before any SQL can run)
    exists = os.path.exists(db_path)
    size = os.path.getsize(db_path) if exists else 0
    results.append(("A1 file exists and >= 1 MB",
                    exists and size >= EXPECTED["min_db_bytes"],
                    f"{size / 1e6:.2f} MB" if exists else "missing"))

    conn = None
    if exists:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)  # READ-ONLY
            conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
            results.append(("A2 opens read-only as SQLite", True, ""))
        except sqlite3.Error as e:
            results.append(("A2 opens read-only as SQLite", False, str(e)))
            conn = None

    if conn is not None:
        for name, fn in CHECKS:
            try:
                ok, detail = fn(conn)
            except Exception as e:              # a crashing check is a failing check
                ok, detail = False, f"{type(e).__name__}: {e}"
            results.append((name, ok, detail))
        conn.close()

    failed = [name for name, ok, _ in results if not ok]
    for name, ok, detail in results:
        print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail else ""))
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return not failed


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=here.parent / "backend" / "movies.db")
    args = parser.parse_args()

    sys.exit(0 if run(args.db_path) else 1)


if __name__ == "__main__":
    main()
