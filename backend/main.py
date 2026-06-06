import os
import sqlite3
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.database import close_db, get_db, load_db, query_database
from backend.schemas import (
    HealthResponse,
    MovieDetail,
    MovieItem,
    MovieSummary,
    PopularResponse,
    RecommendationsResponse,
    SearchResponse,
    SimilarResponse,
    StatsResponse,
    split_genres,
)


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


def to_movie_item(row: dict) -> MovieItem:
    return MovieItem(
        movie_id=row["movie_id"],
        title=row["title"],
        genres=split_genres(row["genres"]),
        year=row["year"],
        poster_path=row["poster_path"],
        rank=row["rank"],
        score=row["score"],
    )


def to_movie_summary(row: dict) -> MovieSummary:
    return MovieSummary(
        movie_id=row["movie_id"],
        title=row["title"],
        genres=split_genres(row["genres"]),
        year=row["year"],
        poster_path=row["poster_path"],
    )


def to_movie_detail(row: dict) -> MovieDetail:
    return MovieDetail(
        movie_id=row["movie_id"],
        title=row["title"],
        genres=split_genres(row["genres"]),
        year=row["year"],
        poster_path=row["poster_path"],
        imdb_id=row["imdb_id"],
        tmdb_id=row["tmdb_id"],
    )


def fetch_popular(db: sqlite3.Connection, limit: int) -> list[MovieItem]:
    rows = query_database(
        db,
        """
        SELECT pm.rank, pm.movie_id, m.title, m.genres, m.year, m.poster_path, pm.score
        FROM popular_movies pm
        JOIN movies m ON m.movie_id = pm.movie_id
        ORDER BY pm.rank
        LIMIT ?
        """,
        (limit,),
    )
    return [to_movie_item(row) for row in rows]


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


@app.get("/health", response_model=HealthResponse)
def get_health(db: sqlite3.Connection = Depends(get_db)):
    try:
        query_database(db, "SELECT 1")
    except sqlite3.Error:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "database": "error"})
    return HealthResponse(status="healthy", database="ok")


@app.get("/stats", response_model=StatsResponse)
def get_stats(db: sqlite3.Connection = Depends(get_db)):
    rows = query_database(db, "SELECT key, value FROM ratings_summary")
    summary = {row["key"]: row["value"] for row in rows}
    return StatsResponse(
        dataset_name=summary["dataset_name"],
        user_count=summary["user_count"],
        movie_count=summary["movie_count"],
        rating_count=summary["rating_count"],
    )


@app.get("/popular", response_model=PopularResponse)
def get_popular(
    limit: int = Query(20, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
):
    return PopularResponse(items=fetch_popular(db, limit))


@app.get("/movies", response_model=SearchResponse)
def search_movies(
    q: str = "",
    limit: int = Query(20, ge=1, le=50),
    db: sqlite3.Connection = Depends(get_db),
):
    search = f"%{q.strip()}%"
    rows = query_database(
        db,
        """
        SELECT movie_id, title, genres, year, poster_path
        FROM movies
        WHERE ? = '%%' OR title LIKE ?
        ORDER BY title
        LIMIT ?
        """,
        (search, search, limit),
    )
    return SearchResponse(query=q, items=[to_movie_summary(row) for row in rows])


@app.get("/movies/{movie_id}", response_model=MovieDetail)
def get_movie(movie_id: int, db: sqlite3.Connection = Depends(get_db)):
    rows = query_database(
        db,
        "SELECT movie_id, title, genres, year, imdb_id, tmdb_id, poster_path FROM movies WHERE movie_id = ?",
        (movie_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="movie not found")
    return to_movie_detail(rows[0])


@app.get("/movies/{movie_id}/similar", response_model=SimilarResponse, response_model_exclude_none=True)
def get_similar_movies(movie_id: int, db: sqlite3.Connection = Depends(get_db)):
    if not query_database(db, "SELECT 1 FROM movies WHERE movie_id = ?", (movie_id,)):
        raise HTTPException(status_code=404, detail="movie not found")

    rows = query_database(
        db,
        """
        SELECT
            ms.rank,
            ms.similar_movie_id AS movie_id,
            m.title,
            m.genres,
            m.year,
            m.poster_path,
            ms.score
        FROM movie_similarity ms
        JOIN movies m ON m.movie_id = ms.similar_movie_id
        WHERE ms.movie_id = ?
        ORDER BY ms.rank
        """,
        (movie_id,),
    )
    if not rows:
        return SimilarResponse(source="fallback", movie_id=movie_id, reason="no_similar_movies", items=[])
    return SimilarResponse(source="similarity", movie_id=movie_id, items=[to_movie_item(row) for row in rows])


@app.get("/users/{user_id}/recommendations", response_model=RecommendationsResponse, response_model_exclude_none=True)
def get_user_recommendations(user_id: int, db: sqlite3.Connection = Depends(get_db)):
    if not query_database(db, "SELECT 1 FROM users WHERE user_id = ?", (user_id,)):
        return RecommendationsResponse(
            source="fallback", user_id=user_id, reason="unknown_user", items=fetch_popular(db, 20)
        )

    rows = query_database(
        db,
        """
        SELECT
            ur.rank,
            ur.movie_id,
            m.title,
            m.genres,
            m.year,
            m.poster_path,
            ur.score
        FROM user_recommendations ur
        JOIN movies m ON m.movie_id = ur.movie_id
        WHERE ur.user_id = ?
        ORDER BY ur.rank
        """,
        (user_id,),
    )
    return RecommendationsResponse(
        source="personalized", user_id=user_id, items=[to_movie_item(row) for row in rows]
    )
