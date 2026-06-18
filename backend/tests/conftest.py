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
#
# Garde d'idempotence (correction DEVELOPER, increment 1 cross-agence, a relire
# par le testeur en phase B) : ce module est ré-exécuté si un test l'importe
# sous un AUTRE nom de module que celui charge par pytest (ex.
# `import tests.conftest` dans le test statique AC22, alors que pytest l'a
# charge comme `conftest`). Sans la sentinelle, ce second import re-supprimait
# le fichier SQLite SOUS le moteur SQLAlchemy deja connecte -> ecritures
# suivantes en `sqlite3.OperationalError: attempt to write a readonly
# database` (faux rouge dependant de l'ordre, pas un artefact sandbox).
if os.environ.get("MVP_TEST_DB_BOOTSTRAPPED") != _tmp_db:
    if os.path.exists(_tmp_db):
        os.remove(_tmp_db)
    os.environ["MVP_TEST_DB_BOOTSTRAPPED"] = _tmp_db

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
def _reset_snapshots_table():
    """Vide `listing_price_snapshots` (et les `comparables`) AVANT chaque test.

    Chantier cross-agence increment 1 (SPEC AC22, lecons 9.7/9.9) : la table de
    snapshots de prix est un etat partage persistant (fichier SQLite jetable de
    la suite). Sans reset, les snapshots/comparables d'un test s'accumulent entre
    tests d'une meme session : un `count()` de snapshots ou un appel repete a
    `save_comparables` sur le meme id deviendrait dependant de l'ordre
    d'execution (faux rouge/vert). On vide AUSSI `comparables` car la logique de
    capture (first_seen immuable, snapshot conditionnel) lit la ligne existante :
    un comparable laisse par un test precedent fausserait la 1re observation du
    suivant.

    Autouse en conftest (jamais en fixture locale, lecon 9.9). Import et reset
    proteges : tant que la table n'existe pas (phase tests-first, avant le code),
    on n'echoue pas a la collecte ; les tests echoueront proprement sur l'absence
    de la colonne/table/endpoint. Reset par DELETE pour ne pas dependre d'un ORM
    eventuellement absent.
    """
    try:
        from db.session import engine
        from sqlalchemy import inspect, text

        insp = inspect(engine)
        with engine.begin() as conn:
            if insp.has_table("listing_price_snapshots"):
                conn.execute(text("DELETE FROM listing_price_snapshots"))
            if insp.has_table("comparables"):
                conn.execute(text("DELETE FROM comparables"))
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_llm_semantic_cache():
    """Vide le cache memoire de llm_semantic AVANT chaque test (chantier
    fix-issue-80, SPEC §3.4 / AC25 ; lecons photo-evidence et 9.9).

    Le filtre deterministe copropriete du fix s'applique AVANT `_set_cache` :
    la valeur mise en cache est la valeur filtree. Un test qui asserte un
    compteur d'appels du client OpenAI mocke (cache hit attendu) ou le contenu
    filtre serait fausse par une entree laissee par un test precedent. Reset
    autouse en conftest GLOBAL, jamais en fixture locale (lecon 9.9). Import
    protege (pattern des autres resets) ; cache pleinement actif intra-test.
    """
    try:
        import app.llm_semantic as llm

        llm._CACHE.clear()
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_routing_cache():
    """Vide le cache memoire de app.routing AVANT chaque test (SPEC contexte-local-v2
    §3 C.1 / §7 ; lecons 9.7 / 9.9 / photo-evidence — JAMAIS en fixture locale).

    `app.routing._CACHE` (TTL 10 min, par process, jamais persiste — CGU Google) est
    un etat partage de module. Plusieurs AC assertent un COMPTEUR d'appels du client
    Google mocke (AC11 cache hit, AC14 deux requetes par mode) : sans reset autouse,
    une entree laissee par un test precedent ferait un cache hit parasite et le mock
    du test suivant ne serait jamais appele -> assertion sur call_count faussee (faux
    rouge/vert dependant de l'ordre). Reset via le point d'entree public
    `reset_routing_cache()` expose par le module (spec §3 C.1). Import protege (sur le
    modele de `_reset_photo_cache`) : tant que `app.routing` n'existe pas (phase
    tests-first), on n'echoue pas a la collecte ; les tests echoueront proprement sur
    l'absence du module / de l'endpoint. Cache pleinement actif intra-test."""
    try:
        from app.routing import reset_routing_cache

        reset_routing_cache()
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
