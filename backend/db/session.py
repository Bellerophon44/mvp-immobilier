from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base

# Connexion SQLite (MVP)
# Le fichier comparables.db est créé automatiquement
DATABASE_URL = "sqlite:///./comparables.db"

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
    """
    Initialise la base de données.
    À appeler au démarrage ou dans les jobs d’ingestion.
    """
    Base.metadata.create_all(bind=engine)
