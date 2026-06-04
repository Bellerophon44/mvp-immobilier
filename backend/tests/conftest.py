import os
import tempfile

# Isolation : base SQLite jetable + clé OpenAI factice AVANT tout import app,
# pour que les tests ne touchent ni la prod ni le réseau.
_tmp_db = os.path.join(tempfile.gettempdir(), "mvp_test_comparables.db")
os.environ.setdefault("DATABASE_PATH", _tmp_db)
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
