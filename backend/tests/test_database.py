from backend.database import query_database


def test_query_database_returns_dict_rows(db):
    rows = query_database(db, "SELECT COUNT(*) AS movie_count FROM movies")

    assert rows == [{"movie_count": 9742}]


def test_loaded_database_is_read_only(db):
    try:
        query_database(db, "CREATE TABLE should_not_exist (id INTEGER)")
    except Exception as exc:
        assert "readonly" in str(exc).lower() or "read-only" in str(exc).lower()
    else:
        raise AssertionError("loaded database accepted a write query")
