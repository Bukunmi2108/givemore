def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "ok"}


def test_root_includes_db_summary(client):
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Hello from backend!"
    assert body["summary"] == {
        "movie_count": "9742",
        "rating_count": "100836",
        "user_count": "610",
    }


def test_stats(client):
    response = client.get("/stats")

    assert response.status_code == 200
    assert response.json() == {
        "dataset_name": "MovieLens Latest Small",
        "user_count": 610,
        "movie_count": 9742,
        "rating_count": 100836,
    }


def test_popular(client):
    response = client.get("/popular")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "popular"
    assert len(body["items"]) == 20
    first = body["items"][0]
    assert first["rank"] == 1
    assert first["movie_id"] == 318  # Shawshank
    assert isinstance(first["genres"], list)
    assert first["poster_path"].startswith("/")  # grids need posters: summary carries the path


def test_popular_rejects_limit_beyond_stored_rows(client):
    response = client.get("/popular", params={"limit": 101})
    assert response.status_code == 422  

def test_search_movies(client):
    response = client.get("/movies", params={"q": "matrix", "limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "matrix"
    assert len(body["items"]) == 2
    assert all("matrix" in movie["title"].lower() for movie in body["items"])
    assert all(isinstance(movie["genres"], list) for movie in body["items"])


def test_search_movies_rejects_oversize_limit(client):
    response = client.get("/movies", params={"limit": 999})
    assert response.status_code == 422


def test_movie_detail(client):
    response = client.get("/movies/1")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Toy Story"
    assert body["year"] == 1995
    assert body["genres"] == ["Adventure", "Animation", "Children", "Comedy", "Fantasy"]
    assert body["imdb_id"] == "0114709"  # zero-padding intact -> imdb.com/title/tt0114709/
    assert body["tmdb_id"] == 862
    assert body["poster_path"].startswith("/")  # image.tmdb.org/t/p/{size}{poster_path}


def test_movie_detail_tmdb_id_is_nullable(client):
    response = client.get("/movies/791")  # one of the 8 movies with no TMDB id

    assert response.status_code == 200
    body = response.json()
    assert body["imdb_id"] == "0113610"
    assert body["tmdb_id"] is None
    assert body["poster_path"] is None  # no tmdb id -> no poster


def test_search_items_stay_lean(client):
    response = client.get("/movies", params={"q": "matrix", "limit": 1})

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert "imdb_id" not in item  # links are detail-page only; list payloads stay summary-shaped


def test_movie_detail_unknown_returns_404(client):
    response = client.get("/movies/999999")
    assert response.status_code == 404


def test_movie_detail_no_genres_serves_empty_list(client):
    response = client.get("/movies/114335")
    assert response.status_code == 200
    assert response.json()["genres"] == []


def test_movie_detail_year_is_nullable(client):
    response = client.get("/movies/176601") 
    assert response.status_code == 200
    assert response.json()["year"] is None


def test_user_recommendations(client):
    response = client.get("/users/1/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "personalized"
    assert body["user_id"] == 1
    assert "reason" not in body
    assert len(body["items"]) == 20
    assert body["items"][0]["rank"] == 1
    assert {"movie_id", "title", "genres", "year", "score", "rank"} <= body["items"][0].keys()


def test_unknown_user_recommendations_fall_back_to_popular(client):
    response = client.get("/users/9999/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "fallback"
    assert body["reason"] == "unknown_user"
    assert body["user_id"] == 9999
    assert len(body["items"]) == 20
    assert body["items"][0]["title"] == "Shawshank Redemption, The"


def test_similar_movies(client):
    response = client.get("/movies/1/similar")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "similarity"
    assert body["movie_id"] == 1
    assert len(body["items"]) == 15
    assert body["items"][0]["rank"] == 1
    assert body["items"][0]["movie_id"] == 3114


def test_similarity_gap_returns_fallback(client):
    response = client.get("/movies/129250/similar") 
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "fallback"
    assert body["reason"] == "no_similar_movies"
    assert body["items"] == []


def test_similar_movies_unknown_movie_returns_404(client):
    response = client.get("/movies/999999/similar")
    assert response.status_code == 404
