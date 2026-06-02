import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db.models import Base


DATABASE_PATH = os.getenv("DATABASE_PATH", "./comparables.db")

db_dir = Path(DATABASE_PATH).parent
if str(db_dir) and not db_dir.exists():
    try:
        db_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# Colonnes ajoutées après la création initiale de la table : create_all ne fait
# pas d'ALTER, donc on rattrape les bases existantes (prod) au démarrage.
_ADD_COLUMNS = {
    "dpe": "ALTER TABLE comparables ADD COLUMN dpe VARCHAR",
    "construction_year": "ALTER TABLE comparables ADD COLUMN construction_year INTEGER",
}


def _migrate_comparables(conn) -> None:
    existing = {row[1] for row in conn.execute(text("PRAGMA table_info(comparables)"))}
    for column, ddl in _ADD_COLUMNS.items():
        if column not in existing:
            conn.execute(text(ddl))


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _migrate_comparables(conn)
