"""Pydantic response models for FastAPI endpoints. These models are used to validate and serialize responses."""

from typing import Literal
from pydantic import BaseModel


def split_genres(genres: str) -> list[str]:
    return [] if genres == "(no genres listed)" else genres.split("|")


class MovieDetail(BaseModel):
    movie_id: int
    title: str
    genres: list[str]
    year: int | None


class MovieItem(MovieDetail):
    rank: int
    score: float


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
    items: list[MovieDetail]
