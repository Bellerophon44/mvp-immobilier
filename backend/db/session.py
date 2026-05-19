import os
from pathlib import Path

from sqlalchemy import create_engine
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


def init_db():
    Base.metadata.create_all(bind=engine)
