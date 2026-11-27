"""Apply additive schema migrations in filename order, once per database."""
from pathlib import Path
from sqlalchemy import text
from backend.database.db import engine

migration_dir = Path(__file__).resolve().parent / 'migrations'
with engine.begin() as connection:
    connection.execute(text('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())'))
for path in sorted(migration_dir.glob('*.sql')):
    with engine.begin() as connection:
        if connection.execute(text('SELECT 1 FROM schema_migrations WHERE name=:name'), {'name': path.name}).scalar():
            continue
        for statement in path.read_text(encoding='utf-8-sig').split(';'):
            if statement.strip():
                connection.execute(text(statement))
        connection.execute(text('INSERT INTO schema_migrations(name) VALUES (:name)'), {'name': path.name})
        print(f'Applied {path.name}')
