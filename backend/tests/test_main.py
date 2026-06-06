def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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


def test_search_movies(client):
    response = client.get("/movies", params={"q": "matrix", "limit": 2})

    assert response.status_code == 200
    movies = response.json()
    assert len(movies) == 2
    assert all("matrix" in movie["title"].lower() for movie in movies)


def test_search_movies_clamps_limit(client):
    response = client.get("/movies", params={"limit": 999})

    assert response.status_code == 200
    assert len(response.json()) == 50


def test_user_recommendations(client):
    response = client.get("/users/1/recommendations")

    assert response.status_code == 200
    recommendations = response.json()
    assert len(recommendations) == 20
    assert recommendations[0]["rank"] == 1
    assert {"movie_id", "title", "genres", "year", "score"} <= recommendations[0].keys()


def test_unknown_user_recommendations_fall_back_to_popular(client):
    response = client.get("/users/9999/recommendations")

    assert response.status_code == 200
    recommendations = response.json()
    assert len(recommendations) == 20
    assert recommendations[0]["rank"] == 1
    assert recommendations[0]["title"] == "Shawshank Redemption, The"


def test_similar_movies(client):
    response = client.get("/movies/1/similar")

    assert response.status_code == 200
    similar = response.json()
    assert len(similar) == 15
    assert similar[0]["rank"] == 1
    assert similar[0]["movie_id"] != 1


def test_similarity_gap_returns_empty_list(client):
    response = client.get("/movies/129250/similar")

    assert response.status_code == 200
    assert response.json() == []
