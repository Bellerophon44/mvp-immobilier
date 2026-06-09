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
def _reset_rate_limit_state():
    # Isolation inter-fichiers de l'etat partage du rate-limit (SPEC 9.9 3.5,
    # lecon 9.7) : le compteur en memoire de module de app.rate_limit doit
    # repartir vide AVANT chaque test, sinon un bucket sature par un fichier
    # (ou un test) pollue les suivants -> faux rouge dependant de l'ordre.
    # Tolerant a l'absence du module (import protege) pour ne pas coupler tous
    # les tests a la presence de la brique rate-limit.
    try:
        from app.rate_limit import reset_rate_limit_state
    except Exception:
        yield
        return
    reset_rate_limit_state()
    yield


@pytest.fixture(autouse=True)
def _reset_events_table():
    """Vide la table `events` AVANT chaque test (SPEC 9.10 §3.8, lecons 9.7/9.9).

    La table `events` est un etat partage persistant (fichier SQLite jetable de
    la suite) : sans reset, les lignes d'un test s'accumulent et un `count()` ou
    un `.one()` filtre devient dependant de l'ordre d'execution -> faux rouge.
    Import protege : tant que le modele `Event` n'existe pas (phase tests-first),
    on n'echoue pas a la collecte ; les tests echoueront proprement sur l'absence
    du modele / de l'endpoint. Le reset se fait via DELETE pour ne pas dependre
    d'un ORM eventuellement absent.
    """
    try:
        from db.session import engine
        from sqlalchemy import inspect, text

        if inspect(engine).has_table("events"):
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM events"))
    except Exception:
        pass
    yield


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
