import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import close_db, get_db, load_db, query_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_db(app)
    try:
        yield
    finally:
        close_db(app)


app = FastAPI(title="givemore", version="0.1.0", lifespan=lifespan)


origins = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=["*"])


@app.get("/")
def read_root(db: sqlite3.Connection = Depends(get_db)):
    summary = query_database(
        db,
        "SELECT key, value FROM ratings_summary WHERE key IN (?, ?, ?)",
        ("movie_count", "user_count", "rating_count"),
    )
    return {
        "message": "Hello from backend!",
        "summary": {row["key"]: row["value"] for row in summary},
    }

@app.get("/health")
def get_health(db: sqlite3.Connection = Depends(get_db)):
    query_database(db, "SELECT 1")
    return {"status": "ok"}


@app.get("/movies")
def search_movies(q: str = "", limit: int = 20, db: sqlite3.Connection = Depends(get_db)):
    limit = max(1, min(limit, 50))
    search = f"%{q.strip()}%"
    return query_database(
        db,
        """
        SELECT movie_id, title, genres, year
        FROM movies
        WHERE ? = '%%' OR title LIKE ?
        ORDER BY title
        LIMIT ?
        """,
        (search, search, limit),
    )


@app.get("/movies/{movie_id}/similar")
def get_similar_movies(movie_id: int, db: sqlite3.Connection = Depends(get_db)):
    return query_database(
        db,
        """
        SELECT
            ms.rank,
            ms.similar_movie_id AS movie_id,
            m.title,
            m.genres,
            m.year,
            ms.score
        FROM movie_similarity ms
        JOIN movies m ON m.movie_id = ms.similar_movie_id
        WHERE ms.movie_id = ?
        ORDER BY ms.rank
        """,
        (movie_id,),
    )


@app.get("/users/{user_id}/recommendations")
def get_user_recommendations(user_id: int, db: sqlite3.Connection = Depends(get_db)):
    recommendations = query_database(
        db,
        """
        SELECT
            ur.rank,
            ur.movie_id,
            m.title,
            m.genres,
            m.year,
            ur.score
        FROM user_recommendations ur
        JOIN movies m ON m.movie_id = ur.movie_id
        WHERE ur.user_id = ?
        ORDER BY ur.rank
        """,
        (user_id,),
    )
    if recommendations:
        return recommendations

    return query_database(
        db,
        """
        SELECT
            pm.rank,
            pm.movie_id,
            m.title,
            m.genres,
            m.year,
            pm.score
        FROM popular_movies pm
        JOIN movies m ON m.movie_id = pm.movie_id
        ORDER BY pm.rank
        LIMIT 20
        """,
    )
