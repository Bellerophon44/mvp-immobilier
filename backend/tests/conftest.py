import os
import tempfile

# Isolation : base SQLite jetable dediee + cle OpenAI factice AVANT tout import
# app, pour que les tests ne touchent ni la prod ni le reseau.
#
# On FORCE (et non setdefault) le chemin de la base de test : un DATABASE_PATH
# preexistant dans l'environnement (dev local, conteneur prod : /data/...) serait
# sinon respecte, puis efface par le os.remove ci-dessous -> suppression
# destructive d'une vraie base. Le fichier porte un suffixe pid pour eviter toute
# collision avec une base reelle et entre executions paralleles.
_tmp_db = os.path.join(
    tempfile.gettempdir(), f"mvp_test_feedback_{os.getpid()}.db"
)
os.environ["DATABASE_PATH"] = _tmp_db
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-used")

# Repartir d'une base vierge a chaque session : sinon les lignes persistees par
# une execution precedente font echouer les assertions d'unicite (ex. .one()
# sur un analysis_id deja insere lors d'un run anterieur).
if os.path.exists(_tmp_db):
    os.remove(_tmp_db)

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _init_db_schema():
    """Cree le schema (table `comparables`, etc.) une fois pour la session.

    Durcissement harnais (testeur, phase B) : `init_db()` n'est appele qu'au
    startup FastAPI (`@app.on_event("startup")`). Les tests qui appellent
    `run_full_analysis` directement (ex. test_photo_evidence) sans jamais
    instancier le `client` declenchaient `OperationalError: no such table:
    comparables` quand ils tournaient AVANT tout test utilisant TestClient.
    La suite ne passait que par chance d'ordre. On force la creation du schema
    ici pour rendre la suite robuste a l'ordre d'execution.
    """
    from db.session import init_db

    init_db()
    yield


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_photo_cache():
    """Vide le cache memoire de photo_evidence entre chaque test. Le cache
    (spec photo-evidence §3.2) est un etat module global : deux tests utilisant le
    meme couple (images capees, claims eligibles) - ex. test_cap_six_images puis
    test_exactly_six_images_all_transmitted, qui se reduisent tous deux a
    cdn.x/0..5.jpg + 'la Moselle' - partageraient une cle de cache et le second
    n'appellerait pas son mock (cache hit), faussant l'assertion sur mock.calls.
    Reset par test = isolation, sans affaiblir la spec (cache toujours actif
    intra-test)."""
    try:
        import app.photo_evidence as pe

        pe._CACHE.clear()
    except Exception:
        pass
    yield
