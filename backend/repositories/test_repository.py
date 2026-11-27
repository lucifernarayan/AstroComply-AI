from backend.repositories.satellite_repository import (
    SatelliteRepository
)

def test_repository_count_matches_catalogue():
    from sqlalchemy import text
    from backend.database.db import engine

    with engine.connect() as conn:
        expected = conn.execute(text("SELECT COUNT(*) FROM satellites")).scalar_one()
    assert SatelliteRepository().get_count() == expected
