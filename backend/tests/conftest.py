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

