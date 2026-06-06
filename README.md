---
title: givemore
emoji: 🎬
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# givemore

A MovieLens movie recommender — simple, reproducible, deployable, and honest about its limits.

**Live:** frontend on Vercel · API on this Hugging Face Space

## How it works

```
MovieLens CSVs ──► offline pipeline ──► movies.db ──► FastAPI (read-only) ──► vanilla-TS frontend
                   (pandas/sklearn)     (SQLite)      (no ML deps)            (Vite, no framework)
```

Everything is **precomputed offline**: item-item collaborative filtering (adjusted cosine,
IUF-weighted, ≥5 co-rating threshold), TF-IDF content similarity, a Bayesian-weighted popularity
fallback, and a precedence blend of the two similarity signals. The API never trains anything —
it serves a 9 MB SQLite artifact that ships with the backend. The frontend treats MovieLens user
IDs as demo profiles; unknown visitors get labeled popularity fallbacks.

## Repo layout

| dir | what | heavy deps |
|---|---|---|
| `pipeline/` | EDA + build (`build_db.py`), artifact guard (`validate_db.py`, 37 checks), TMDB poster enrichment (`fetch_posters.py`) | pandas, numpy, scikit-learn |
| `backend/` | FastAPI over `movies.db`, read-only connection, 20 tests | fastapi only |
| `frontend/` | Two-page vanilla-TS MPA (Vite): recommendations + search, movie page with similar titles, 13 vitest specs | none |

## Run it locally

```bash
# 1. data: download MovieLens latest-small into data/  (https://grouplens.org/datasets/movielens/)
# 2. posters (optional, needs a free TMDB key in pipeline/.env): python pipeline/fetch_posters.py
# 3. build + validate the artifact
cd pipeline && uv run python build_db.py && python3 validate_db.py
# 4. backend
cd ../  && uv run --project backend fastapi dev backend/main.py     # :8000
# 5. frontend
cd frontend && npm install && npm run dev                            # :5173
```

## Attribution

- Movie data: [MovieLens](https://grouplens.org/datasets/movielens/) (ml-latest-small) by
  [GroupLens Research](https://grouplens.org/), University of Minnesota. Used for
  research/education; see their README for terms.
- This product uses the [TMDB](https://www.themoviedb.org) API for poster images but is not
  endorsed or certified by TMDB.
