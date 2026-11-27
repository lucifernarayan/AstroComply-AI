from sqlalchemy import text
from backend.database.db import engine

def test_postgresql_connection():
    with engine.connect() as conn:
        assert conn.execute(text("SELECT current_database()")).scalar_one()
