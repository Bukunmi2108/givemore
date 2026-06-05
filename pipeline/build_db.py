"""Build movies.db from the MovieLens latest-small CSVs.

Ported from build.ipynb -- every stage, formula, and assert mirrors the
notebook. The asserts are deliberate: they encode measured invariants from
the EDA (see plan.md §1.1), so a bad/truncated input fails loudly.

Usage:
    python build_db.py [--data-dir ../data] [--db-path ../backend/movies.db]
"""

import argparse
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

# --- Config: decisions made during EDA (plan.md §1.1) ---
M_SMOOTHING = 25        # Bayesian popularity smoothing (Q7)
MIN_CO_RATINGS = 5      # min shared raters before a CF similarity is trusted (Q1)
MIN_MOVIE_RATES = 5     # a movie needs >=5 ratings to be a CF candidate (Q3)
TOP_N_USER_RECS = 20
TOP_N_SIMILAR = 15
W_COLLAB = 0.75
W_CONTENT = 0.25
BLOCK = 512             # row-block size for content top-k


# --- Stage 1: load + integrity ---
def load(data_dir):
    ratings = pd.read_csv(data_dir / "ratings.csv")
    movies = pd.read_csv(data_dir / "movies.csv")
    links = pd.read_csv(data_dir / "links.csv")

    assert set(ratings.columns) == {"userId", "movieId", "rating", "timestamp"}
    assert set(movies.columns) == {"movieId", "title", "genres"}
    assert set(links.columns) == {"movieId", "imdbId", "tmdbId"}

    assert ratings["userId"].nunique() == 610
    assert movies["movieId"].nunique() == 9742
    assert links["movieId"].nunique() == 9742

    assert set(ratings.movieId) - set(movies.movieId) == set()
    assert set(movies.movieId) - set(links.movieId) == set()
    assert ratings[["userId", "movieId"]].duplicated().sum() == 0
    return ratings, movies, links


# --- Stage 2: clean movie metadata ---
def clean_movies(movies):
    movies["raw_title"] = movies["title"].str.replace(r"\s+", " ", regex=True).str.strip()
    movies["Year"] = movies["raw_title"].str.extract(r"\((\d{4})(?:[–-]\d{4})?\)\s*$", expand=False)
    movies["title"] = movies["raw_title"].str.replace(r"\s*\(\d{4}(?:[–-]\d{4})?\)\s*$", "", regex=True)
    movies.drop(columns=["raw_title"], inplace=True)

    assert movies["Year"].isna().sum() == 12

    movies["genre_list"] = movies["genres"].str.split("|")
    movies["genre_list"] = movies["genre_list"].apply(
        lambda genres: [g for g in genres if g != "(no genres listed)"]
    )
    assert (movies["genres"] == "(no genres listed)").sum() == 34
    return movies


# --- Stage 3: derived rating statistics ---
def compute_stats(ratings):
    C = ratings["rating"].mean()
    movie_stats = ratings.groupby("movieId")["rating"].agg(["count", "mean"])
    user_stats = ratings.groupby("userId")["rating"].agg(["count", "mean"])

    assert user_stats.shape[0] == 610
    assert movie_stats.shape[0] == 9724
    assert C == 3.501556983616962
    return C, movie_stats, user_stats


# --- Stage 4: popular fallback ---
def weighted_score(v, R, C, m):
    return (v / (v + m)) * R + (m / (v + m)) * C


def popular_fallback(movie_stats, C):
    weighted_scores = movie_stats.apply(
        lambda row: weighted_score(row["count"], row["mean"], C, M_SMOOTHING), axis=1
    ).sort_values(ascending=False)

    assert weighted_scores.shape[0] == 9724
    assert weighted_scores.index[0] == 318  # Shawshank
    assert np.isclose(weighted_scores.iloc[0], 4.361224925702994)
    return weighted_scores


# --- Stage 5: rating matrices ---
def rating_matrices(ratings, user_stats):
    R = ratings.pivot_table(index="userId", columns="movieId", values="rating")
    movie_index = R.columns.to_numpy()
    user_index = R.index.to_numpy()

    B = R.notna().astype(float)
    co_ratings = (B.T @ B).to_numpy().copy()
    np.fill_diagonal(co_ratings, 0)

    Mc = R.sub(user_stats["mean"], axis=0).fillna(0.0).to_numpy()

    assert R.shape == (610, 9724)
    assert co_ratings.shape == (9724, 9724)
    assert Mc.shape == (610, 9724)
    assert (co_ratings >= MIN_CO_RATINGS).sum() // 2 == 1_293_963
    return R, B, co_ratings, Mc, movie_index, user_index


# --- Stage 6: collaborative similarity (adjusted cosine + IUF) ---
def collab_similarity(R, Mc, co_ratings, movie_stats, user_stats, movie_index):
    N_movies = R.shape[1]
    w = np.log(N_movies / user_stats["count"].to_numpy())

    W = Mc * np.sqrt(w)[:, None]
    cand = movie_stats["count"].reindex(movie_index).to_numpy() >= MIN_MOVIE_RATES
    Wc = W[:, cand]
    cand_movies = movie_index[cand]

    norms = np.linalg.norm(Wc, axis=0)
    Wn = Wc / np.where(norms == 0, 1, norms)

    collab_sim = Wn.T @ Wn
    np.fill_diagonal(collab_sim, 0.0)
    collab_sim[co_ratings[np.ix_(cand, cand)] < MIN_CO_RATINGS] = 0.0

    assert (collab_sim != 0).any(axis=1).sum() == 3634

    collab_sim_clip = np.clip(collab_sim, 0, 1)  # scale reconciliation (Stage 8)
    return collab_sim_clip, cand, cand_movies


# --- Stage 7: content similarity (TF-IDF over genres + title tokens) ---
def content_similarity(movies):
    docs = movies["title"] + " " + movies["genre_list"].apply(lambda g: " ".join(g))
    tfidf = TfidfVectorizer(min_df=2)
    tfX = tfidf.fit_transform(docs)

    n = tfX.shape[0]
    mids = movies["movieId"].to_numpy()
    content_neighbors = {}
    for start in range(0, n, BLOCK):
        sims = (tfX[start:start + BLOCK] @ tfX.T).toarray()
        for r in range(sims.shape[0]):
            i = start + r
            sims[r, i] = 0.0
            k = TOP_N_SIMILAR
            idx = np.argpartition(sims[r], -k)[-k:]
            idx = idx[np.argsort(sims[r][idx])[::-1]]
            content_neighbors[int(mids[i])] = [
                (int(mids[j]), float(sims[r][j])) for j in idx if sims[r][j] > 0
            ]

    assert content_neighbors.keys() == set(movies["movieId"])
    return tfX, content_neighbors, mids


# --- Stage 8: hybrid blend (precedence: CF tier first, content fills) ---
def blend(tfX, content_neighbors, mids, collab_sim_clip, cand_movies):
    tfpos = {int(m): k for k, m in enumerate(mids)}
    cand_pos = {int(m): k for k, m in enumerate(cand_movies)}

    rows = []
    for m in mids:
        m = int(m)
        cf = []
        covered = set()
        if m in cand_pos:
            ci = cand_pos[m]
            nbr = np.where(collab_sim_clip[ci] > 0)[0]
            if len(nbr):
                cvec = (tfX[tfpos[m]] @ tfX[[tfpos[int(cand_movies[cj])] for cj in nbr]].T).toarray().ravel()
                for cj, cs in zip(nbr, cvec):
                    jm = int(cand_movies[cj])
                    cf.append((jm, W_COLLAB * collab_sim_clip[ci, cj] + W_CONTENT * float(cs)))
                    covered.add(jm)
            cf.sort(key=lambda kv: kv[1], reverse=True)
        fill = [(j, cs) for j, cs in content_neighbors[m] if j not in covered]
        for rank, (j, score) in enumerate((cf + fill)[:TOP_N_SIMILAR], 1):
            rows.append((m, rank, j, float(score)))

    movie_similarity = pd.DataFrame(rows, columns=["movie_id", "rank", "similar_movie_id", "score"])

    assert (movie_similarity["movie_id"] != movie_similarity["similar_movie_id"]).all()
    # rank is the authoritative order (NOT score - tier boundary can break global descending)
    assert movie_similarity.groupby("movie_id")["rank"].apply(
        lambda r: sorted(r) == list(range(1, len(r) + 1))
    ).all()
    # expected gap: exactly 5 movies (min_df=2 empty-vector films) get no rows
    assert movie_similarity["movie_id"].nunique() == 9742 - 5
    return movie_similarity


# --- Stage 9: user recommendations (vote tally + popularity padding) ---
def user_recs(ratings, B, Mc, cand, cand_movies, collab_sim_clip, user_index, weighted_scores):
    S = Mc[:, cand] @ collab_sim_clip

    rated_mask = B.to_numpy()[:, cand].astype(bool)
    S_masked = np.where(rated_mask, -np.inf, S)

    rated_by_user = ratings.groupby("userId")["movieId"].agg(set)

    urec = []
    pad_users = []
    for u in range(S_masked.shape[0]):
        uid, row = int(user_index[u]), S_masked[u]
        k = min(TOP_N_USER_RECS, int((row > 0).sum()))  # only positive evidence counts
        top = np.argpartition(row, -k)[-k:] if k else np.array([], dtype=int)
        top = top[np.argsort(row[top])[::-1]]
        recs = [(int(cand_movies[i]), float(row[i])) for i in top]
        if len(recs) < TOP_N_USER_RECS:  # pad with popularity
            pad_users.append(uid)
            have = {m for m, _ in recs} | rated_by_user[uid]
            for pm, psc in weighted_scores.items():
                if len(recs) >= TOP_N_USER_RECS:
                    break
                if int(pm) not in have:
                    recs.append((int(pm), float(psc)))
        urec += [(uid, r, m, sc) for r, (m, sc) in enumerate(recs, 1)]

    user_recommendations = pd.DataFrame(urec, columns=["user_id", "rank", "movie_id", "score"])

    per_user = user_recommendations.groupby("user_id").size()
    assert per_user.shape[0] == 610 and (per_user == TOP_N_USER_RECS).all()
    assert sum(
        m in rated_by_user[u]
        for u, m in zip(user_recommendations["user_id"], user_recommendations["movie_id"])
    ) == 0
    assert pad_users == [53]  # the all-5.0 rater: centered profile all zeros -> CF mute
    assert int(user_recommendations.loc[user_recommendations["user_id"] == 53, "movie_id"].iloc[0]) == 318
    return user_recommendations


# --- Stage 10: ratings_summary ---
def build_summary(ratings, movies):
    return pd.DataFrame(
        [
            ("dataset_name", "MovieLens Latest Small"),
            ("rating_count", str(len(ratings))),
            ("movie_count", str(movies["movieId"].nunique())),
            ("user_count", str(ratings["userId"].nunique())),
            ("generated_at", datetime.now(timezone.utc).isoformat()),
        ],
        columns=["key", "value"],
    )


# --- Stage 11: assemble output tables + write SQLite ---
def assemble_tables(movies, user_stats, movie_stats, weighted_scores):
    # movies table from Stage-2 metadata (all 9,742 - NOT movie_stats, missing the 18 unrated)
    movies_table = movies[["movieId", "title", "genres", "Year"]].rename(
        columns={"movieId": "movie_id", "Year": "year"}
    )
    movies_table["year"] = pd.to_numeric(movies_table["year"]).astype("Int64")  # nullable

    users_table = user_stats.reset_index().rename(
        columns={"userId": "user_id", "count": "rating_count", "mean": "avg_rating"}
    )

    top_pop = weighted_scores.head(100)
    popular_movies = pd.DataFrame({
        "rank": np.arange(1, len(top_pop) + 1),
        "movie_id": top_pop.index.astype(int),
        "score": top_pop.to_numpy(),
        "rating_count": movie_stats.loc[top_pop.index, "count"].to_numpy(),
        "avg_rating": movie_stats.loc[top_pop.index, "mean"].to_numpy(),
    })

    assert movies_table.shape[0] == 9742
    assert users_table.shape[0] == 610
    assert popular_movies.shape[0] == 100
    return movies_table, users_table, popular_movies


DDL = """
CREATE TABLE movies (
    movie_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    genres TEXT NOT NULL,
    year INTEGER
);
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    rating_count INTEGER NOT NULL,
    avg_rating REAL NOT NULL
);
CREATE TABLE popular_movies (
    "rank" INTEGER PRIMARY KEY,
    movie_id INTEGER NOT NULL,
    score REAL NOT NULL,
    rating_count INTEGER NOT NULL,
    avg_rating REAL NOT NULL,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id)
);
CREATE TABLE user_recommendations (
    user_id INTEGER NOT NULL,
    "rank" INTEGER NOT NULL,
    movie_id INTEGER NOT NULL,
    score REAL NOT NULL,
    PRIMARY KEY (user_id, "rank"),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id)
);
CREATE TABLE movie_similarity (
    movie_id INTEGER NOT NULL,
    "rank" INTEGER NOT NULL,
    similar_movie_id INTEGER NOT NULL,
    score REAL NOT NULL,
    PRIMARY KEY (movie_id, "rank"),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id),
    FOREIGN KEY (similar_movie_id) REFERENCES movies(movie_id)
);
CREATE TABLE ratings_summary (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE INDEX idx_user_recommendations_user_id ON user_recommendations(user_id);
CREATE INDEX idx_movie_similarity_movie_id ON movie_similarity(movie_id);
CREATE INDEX idx_movies_title ON movies(title);
CREATE INDEX idx_popular_movies_rank ON popular_movies("rank");
"""


def write_db(db_path, movies_table, users_table, popular_movies,
             user_recommendations, movie_similarity, ratings_summary):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.executescript(DDL)

    movies_table.to_sql("movies", conn, index=False, if_exists="append")
    users_table.to_sql("users", conn, index=False, if_exists="append")
    popular_movies.to_sql("popular_movies", conn, index=False, if_exists="append")
    user_recommendations.to_sql("user_recommendations", conn, index=False, if_exists="append")
    movie_similarity.to_sql("movie_similarity", conn, index=False, if_exists="append")
    ratings_summary.to_sql("ratings_summary", conn, index=False, if_exists="append")

    conn.commit()
    conn.close()
    print(f"wrote {db_path}: {os.path.getsize(db_path) / 1e6:.2f} MB")


# --- Stage 12: validate the written DB (seed of validate_db.py) ---
def validate_db(db_path):
    conn = sqlite3.connect(db_path)

    def q(sql):
        return pd.read_sql_query(sql, conn)

    tables = set(q("SELECT name FROM sqlite_master WHERE type='table'")["name"])
    assert {"movies", "users", "popular_movies", "user_recommendations",
            "movie_similarity", "ratings_summary"} <= tables

    # referential integrity on the generated DB (re-assert Q17 downstream)
    assert q("SELECT COUNT(*) n FROM user_recommendations ur LEFT JOIN movies m ON ur.movie_id = m.movie_id WHERE m.movie_id IS NULL")["n"][0] == 0
    assert q("SELECT COUNT(*) n FROM movie_similarity ms LEFT JOIN movies m ON ms.similar_movie_id = m.movie_id WHERE m.movie_id IS NULL")["n"][0] == 0

    # no self-similarity; ranks unique per group
    assert q("SELECT COUNT(*) n FROM movie_similarity WHERE movie_id = similar_movie_id")["n"][0] == 0
    assert q('SELECT COUNT(*) n FROM (SELECT movie_id FROM movie_similarity GROUP BY movie_id, "rank" HAVING COUNT(*) > 1)')["n"][0] == 0
    assert q('SELECT COUNT(*) n FROM (SELECT user_id FROM user_recommendations GROUP BY user_id, "rank" HAVING COUNT(*) > 1)')["n"][0] == 0

    # coverage
    assert q("SELECT COUNT(*) n FROM movies")["n"][0] == 9742
    assert q("SELECT COUNT(*) n FROM users")["n"][0] == 610
    assert q("SELECT COUNT(DISTINCT user_id) n FROM user_recommendations")["n"][0] == 610
    assert q("SELECT COUNT(*) n FROM user_recommendations")["n"][0] == 610 * TOP_N_USER_RECS
    assert q("SELECT COUNT(DISTINCT movie_id) n FROM movie_similarity")["n"][0] == 9742 - 5  # 5 expected empty-vector gaps
    assert q("SELECT COUNT(*) n FROM popular_movies")["n"][0] == 100

    conn.close()
    print("all DB validation checks passed")


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=here.parent / "data")
    parser.add_argument("--db-path", type=Path, default=here.parent / "backend" / "movies.db")
    args = parser.parse_args()

    print("stage 1: load + integrity")
    ratings, movies, _links = load(args.data_dir)  # links only needed for integrity checks

    print("stage 2: clean movie metadata")
    movies = clean_movies(movies)

    print("stage 3: derived rating statistics")
    C, movie_stats, user_stats = compute_stats(ratings)

    print("stage 4: popular fallback")
    weighted_scores = popular_fallback(movie_stats, C)

    print("stage 5: rating matrices")
    R, B, co_ratings, Mc, movie_index, user_index = rating_matrices(ratings, user_stats)

    print("stage 6: collaborative similarity (adjusted cosine + IUF)")
    collab_sim_clip, cand, cand_movies = collab_similarity(
        R, Mc, co_ratings, movie_stats, user_stats, movie_index
    )

    print("stage 7: content similarity (TF-IDF)")
    tfX, content_neighbors, mids = content_similarity(movies)

    print("stage 8: hybrid blend -> movie_similarity")
    movie_similarity = blend(tfX, content_neighbors, mids, collab_sim_clip, cand_movies)

    print("stage 9: user recommendations")
    user_recommendations = user_recs(
        ratings, B, Mc, cand, cand_movies, collab_sim_clip, user_index, weighted_scores
    )

    print("stage 10: ratings_summary")
    ratings_summary = build_summary(ratings, movies)

    print("stage 11: assemble tables + write SQLite")
    movies_table, users_table, popular_movies = assemble_tables(
        movies, user_stats, movie_stats, weighted_scores
    )
    write_db(args.db_path, movies_table, users_table, popular_movies,
             user_recommendations, movie_similarity, ratings_summary)

    print("stage 12: validate written DB")
    validate_db(args.db_path)


if __name__ == "__main__":
    main()
