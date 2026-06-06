"""Pydantic response models for FastAPI endpoints. These models are used to validate and serialize responses."""

from typing import Literal
from pydantic import BaseModel


def split_genres(genres: str) -> list[str]:
    return [] if genres == "(no genres listed)" else genres.split("|")


class MovieSummary(BaseModel):
    movie_id: int
    title: str
    genres: list[str]
    year: int | None
    poster_path: str | None  # TMDB path ("/abc.jpg"); frontend prefixes image.tmdb.org/t/p/{size}


class MovieItem(MovieSummary):
    rank: int
    score: float


class MovieDetail(MovieSummary):
    imdb_id: str  # zero-padded, e.g. "0114709" -> imdb.com/title/tt0114709/
    tmdb_id: int | None  # 8 movies have no TMDB id


class HealthResponse(BaseModel):
    status: str
    database: str


class StatsResponse(BaseModel):
    dataset_name: str
    user_count: int
    movie_count: int
    rating_count: int


class PopularResponse(BaseModel):
    source: Literal["popular"] = "popular"
    items: list[MovieItem]


class RecommendationsResponse(BaseModel):
    source: Literal["personalized", "fallback"]
    user_id: int
    reason: str | None = None 
    items: list[MovieItem]


class SimilarResponse(BaseModel):
    source: Literal["similarity", "fallback"]
    movie_id: int
    reason: str | None = None
    items: list[MovieItem]


class SearchResponse(BaseModel):
    query: str
    items: list[MovieSummary]
