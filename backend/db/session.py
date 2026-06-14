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
    "postal_code": "ALTER TABLE comparables ADD COLUMN postal_code VARCHAR",
    "floor": "ALTER TABLE comparables ADD COLUMN floor INTEGER",
    "has_elevator": "ALTER TABLE comparables ADD COLUMN has_elevator BOOLEAN",
    "has_terrace": "ALTER TABLE comparables ADD COLUMN has_terrace BOOLEAN",
    "has_balcony": "ALTER TABLE comparables ADD COLUMN has_balcony BOOLEAN",
    "is_condo": "ALTER TABLE comparables ADD COLUMN is_condo BOOLEAN",
    "condo_fees": "ALTER TABLE comparables ADD COLUMN condo_fees FLOAT",
    "has_cellar": "ALTER TABLE comparables ADD COLUMN has_cellar BOOLEAN",
    "parking": "ALTER TABLE comparables ADD COLUMN parking INTEGER",
    "bedrooms": "ALTER TABLE comparables ADD COLUMN bedrooms INTEGER",
    "first_seen_at": "ALTER TABLE comparables ADD COLUMN first_seen_at DATETIME",
    "last_seen_at": "ALTER TABLE comparables ADD COLUMN last_seen_at DATETIME",
    # Re-link "sans photo" meme agence (increment 2a) — identifiants techniques
    # internes. lineage_id est indexe via le CREATE INDEX idempotent ci-dessous
    # (un ALTER ADD COLUMN ne pose pas l'index sur une base prod existante).
    "reference": "ALTER TABLE comparables ADD COLUMN reference VARCHAR",
    "customer_id": "ALTER TABLE comparables ADD COLUMN customer_id VARCHAR",
    "lineage_id": "ALTER TABLE comparables ADD COLUMN lineage_id VARCHAR",
    # URLs photo captees a la collecte (increment 2b etape 1) — metadonnee
    # interne nullable, pas d'index.
    "photo_urls": "ALTER TABLE comparables ADD COLUMN photo_urls VARCHAR",
}


def _migrate_comparables(conn) -> None:
    existing = {row[1] for row in conn.execute(text("PRAGMA table_info(comparables)"))}
    for column, ddl in _ADD_COLUMNS.items():
        if column not in existing:
            conn.execute(text(ddl))
    # Index sur lineage_id pour une base prod EXISTANTE (table deja creee, colonne
    # ajoutee par ALTER ci-dessus) : create_all ne le pose que sur une base neuve.
    # IF NOT EXISTS garantit l'idempotence (re-run sans erreur), apres les ALTER.
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_comparables_lineage_id "
            "ON comparables (lineage_id)"
        )
    )
    # Index sur reference (meme raison) : la recherche de lignee filtre par
    # reference egale pour chaque annonce neuve. Sans index, balayage de table
    # par insertion -> ingestion O(n*m) qui finit en timeout/500 a l'echelle.
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_comparables_reference "
            "ON comparables (reference)"
        )
    )


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _migrate_comparables(conn)
