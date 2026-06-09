"""Tests du critere 9.9 — rate-limit en memoire sur /analyze et /feedback.

Contrat : docs/specs/9.9-SPEC.md §4 (12 criteres d'acceptation).

Phase A (tests-first) : ROUGE LEGITIME attendu tant que la fonctionnalite
n'existe pas. Les echecs doivent porter sur l'ABSENCE de la brique de
rate-limit (pas de 429 emis, import de app.rate_limit qui echoue), pas sur
des erreurs de syntaxe / harnais.

Contrat de testabilite exige du developpeur (cf. SPEC §3.1 et §3.5) :
- module `app/rate_limit.py` exposant une FABRIQUE de dependance parametrable
  `rate_limiter(limit: int, window_seconds: float) -> Callable` utilisable via
  `Depends(...)`, qui leve `HTTPException(429, headers={"Retry-After": "<n>"})`
  au-dela du seuil ;
- un point de reinitialisation de l'etat memoire :
  `reset_rate_limit_state()` (vide tous les buckets). Utilise par la fixture
  autouse ci-dessous pour l'isolation (lecon 9.7 : etat partage de module).
- `/analyze` cable a limit=10/window=60, `/feedback` a limit=60/window=60.

Aucune attente de `time.sleep(60)` reel : le glissement de fenetre est teste
via une dependance dediee a fenetre tres courte (brique reutilisable montee
sur une mini-app jetable) — la SPEC garantit la fenetre parametrable.
"""

import logging

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

IP_A = "203.0.113.7"
IP_B = "203.0.113.9"

ANALYZE_LIMIT = 10
FEEDBACK_LIMIT = 60

VALID_ANALYZE_BODY = {"raw_text": "Appartement T3 a Metz, 70 m2, 250000 EUR."}
VALID_FEEDBACK_BODY = {"rating": 3}

EXPECTED_REQUIREMENTS = {
    "fastapi",
    "uvicorn[standard]",
    "sqlalchemy",
    "requests",
    "beautifulsoup4",
    "openai",
    "numpy",
}


# ---------------------------------------------------------------------------
# Isolation (lecon 9.7) : on vide l'etat memoire du limiteur AVANT chaque test.
# Fixture locale au fichier (autouse) pour ne pas toucher conftest tant que ce
# n'est pas strictement necessaire. Si le module n'existe pas encore, on skip
# proprement le reset (le test echouera de toute facon sur l'absence de 429).
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    try:
        from app.rate_limit import reset_rate_limit_state
    except Exception:
        yield
        return
    reset_rate_limit_state()
    yield
    reset_rate_limit_state()


# ---------------------------------------------------------------------------
# Mock de la couche d'analyse : on teste le rate-limit, PAS le pipeline LLM.
# Sans ce mock, /analyze partirait sur un appel reseau OpenAI reel.
# ---------------------------------------------------------------------------
@pytest.fixture()
def analyze_client(client, monkeypatch):
    def _fake_analysis(*args, **kwargs):
        return {
            "global_score": 75,
            "verdict": "A creuser",
            "confidence": "Moyenne",
            "pillars": [],
            "actions": {"questions": [], "negotiation": []},
            "local_context": None,
        }

    import app.main as main_mod

    monkeypatch.setattr(main_mod, "run_full_analysis", _fake_analysis)
    return client


def _post_analyze(c, ip, body=None):
    return c.post(
        "/analyze",
        json=VALID_ANALYZE_BODY if body is None else body,
        headers={"Fly-Client-IP": ip},
    )


def _post_feedback(c, ip, body=None):
    return c.post(
        "/feedback",
        json=VALID_FEEDBACK_BODY if body is None else body,
        headers={"Fly-Client-IP": ip},
    )


# --- Critere 1 : sous le seuil /analyze, jamais 429 (1 a 10) -------------
def test_analyze_under_threshold_never_429(analyze_client):
    for i in range(1, ANALYZE_LIMIT + 1):
        resp = _post_analyze(analyze_client, IP_A)
        assert resp.status_code != 429, f"requete {i} ne doit pas etre 429"


# --- Critere 2 : la 11e requete /analyze meme IP -> 429 ------------------
def test_analyze_eleventh_request_blocked(analyze_client):
    for _ in range(ANALYZE_LIMIT):
        _post_analyze(analyze_client, IP_A)
    resp = _post_analyze(analyze_client, IP_A)
    assert resp.status_code == 429


# --- Critere 3 : en-tete Retry-After present, entier 1..60 --------------
def test_analyze_429_has_retry_after(analyze_client):
    resp = None
    for _ in range(ANALYZE_LIMIT + 1):
        resp = _post_analyze(analyze_client, IP_A)
    assert resp.status_code == 429
    header_keys = {k.lower() for k in resp.headers}
    assert "retry-after" in header_keys
    retry_after = int(resp.headers["retry-after"])
    assert 1 <= retry_after <= 60


# --- Critere 4 : buckets par IP distincts -------------------------------
def test_analyze_buckets_per_ip_isolated(analyze_client):
    for _ in range(ANALYZE_LIMIT + 1):
        _post_analyze(analyze_client, IP_A)
    blocked = _post_analyze(analyze_client, IP_A)
    assert blocked.status_code == 429

    other = _post_analyze(analyze_client, IP_B)
    assert other.status_code != 429, "IP B ne doit pas heriter du blocage de IP A"


# --- Critere 6 : /feedback a une limite plus large que /analyze ---------
def test_feedback_wider_limit_than_analyze(client):
    # La 11e requete /feedback (au seuil strict d'/analyze) doit passer.
    for _ in range(ANALYZE_LIMIT):
        _post_feedback(client, IP_A)
    eleventh = _post_feedback(client, IP_A)
    assert eleventh.status_code != 429, "limite /feedback ne doit pas etre 10"


def test_feedback_blocks_at_its_own_threshold(client):
    statuses = []
    for _ in range(FEEDBACK_LIMIT + 1):
        statuses.append(_post_feedback(client, IP_A).status_code)
    # 1..60 ne sont jamais 429 ; la 61e l'est.
    assert all(s != 429 for s in statuses[:FEEDBACK_LIMIT])
    assert statuses[FEEDBACK_LIMIT] == 429


# --- Critere 7 : l'IP n'apparait dans aucun log -------------------------
def test_ip_never_logged_fly_client_ip(analyze_client, caplog):
    with caplog.at_level(logging.DEBUG):
        for _ in range(ANALYZE_LIMIT + 1):
            _post_analyze(analyze_client, IP_A)
    assert IP_A not in caplog.text


def test_ip_never_logged_x_forwarded_for(analyze_client, caplog):
    fwd_ip = "198.51.100.5"
    with caplog.at_level(logging.DEBUG):
        for _ in range(ANALYZE_LIMIT + 1):
            analyze_client.post(
                "/analyze",
                json=VALID_ANALYZE_BODY,
                headers={"X-Forwarded-For": f"{fwd_ip}, 10.0.0.1"},
            )
    assert fwd_ip not in caplog.text


# --- Critere 8 : aucune nouvelle dependance -----------------------------
def test_requirements_no_new_dependency():
    import os

    req_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "requirements.txt",
    )
    with open(req_path, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    assert len(lines) == 7, "requirements.txt doit garder 7 lignes non vides"

    def _name(line):
        for sep in ("==", ">=", "<=", "~=", ">", "<"):
            if sep in line:
                return line.split(sep)[0].strip()
        return line.strip()

    names = {_name(ln) for ln in lines}
    assert names == EXPECTED_REQUIREMENTS
    assert "slowapi" not in {n.lower() for n in names}


# --- Critere 9 : contrat /analyze inchange (body {} -> 400, pas 429/500) -
def test_analyze_contract_unchanged_empty_body(analyze_client):
    resp = analyze_client.post(
        "/analyze", json={}, headers={"Fly-Client-IP": IP_A}
    )
    assert resp.status_code == 400


def test_analyze_golden_path_schema_preserved(analyze_client):
    resp = _post_analyze(analyze_client, IP_A)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {
        "global_score",
        "verdict",
        "confidence",
        "pillars",
        "actions",
    }


# --- Critere 10 : contrat /feedback inchange ----------------------------
def test_feedback_contract_unchanged_ok(client):
    resp = _post_feedback(client, IP_A)
    assert resp.status_code == 201
    assert resp.json() == {"status": "ok"}


def test_feedback_contract_unchanged_validation(client):
    resp = client.post(
        "/feedback", json={"rating": 6}, headers={"Fly-Client-IP": IP_A}
    )
    assert resp.status_code == 422


# --- Critere 11 : repli d'IP via X-Forwarded-For (premier hop) ----------
def test_ip_fallback_x_forwarded_for_first_hop(analyze_client):
    hop_a = "198.51.100.5"
    hop_b = "198.51.100.99"

    last = None
    for _ in range(ANALYZE_LIMIT + 1):
        last = analyze_client.post(
            "/analyze",
            json=VALID_ANALYZE_BODY,
            headers={"X-Forwarded-For": f"{hop_a}, 10.0.0.1"},
        )
    assert last.status_code == 429, "le premier hop XFF doit servir de bucket"

    other = analyze_client.post(
        "/analyze",
        json=VALID_ANALYZE_BODY,
        headers={"X-Forwarded-For": f"{hop_b}, 10.0.0.1"},
    )
    assert other.status_code != 429, "un autre premier hop n'est pas bloque"


def test_no_header_does_not_crash(analyze_client):
    # Sans aucun en-tete, request.client.host sert de cle : pas de 500.
    resp = analyze_client.post("/analyze", json=VALID_ANALYZE_BODY)
    assert resp.status_code != 500


# --- Critere 12 : reinitialisation entre tests effective ----------------
# Deux tests consecutifs saturent la MEME IP ; grace a la fixture autouse,
# chacun repart d'un etat vide -> leur 1re requete n'est jamais 429.
def test_reset_isolation_first_call(analyze_client):
    first = _post_analyze(analyze_client, IP_A)
    assert first.status_code != 429
    for _ in range(ANALYZE_LIMIT + 1):
        _post_analyze(analyze_client, IP_A)


def test_reset_isolation_second_call(analyze_client):
    # Si l'etat n'etait pas reinitialise, le test precedent aurait sature IP_A
    # et cette 1re requete serait deja 429.
    first = _post_analyze(analyze_client, IP_A)
    assert first.status_code != 429


# --- Critere 5 : la fenetre glisse (brique reutilisable, fenetre courte) -
# On teste la BRIQUE directement (dependance parametrable montee sur une
# mini-app jetable) avec une fenetre tres courte, sans toucher au cablage
# 60s d'/analyze et SANS time.sleep(60).
def _build_short_window_app(limit, window_seconds):
    from app.rate_limit import rate_limiter

    app = FastAPI()

    @app.get("/ping")
    def ping(_=Depends(rate_limiter(limit=limit, window_seconds=window_seconds))):
        return {"ok": True}

    return app


def test_sliding_window_reopens_clock_mocked(monkeypatch):
    # Glissement deterministe : on mocke la source de temps (time.monotonic) au
    # lieu d'attendre une duree reelle (pas de time.sleep, pas de flakiness sur
    # machine lente). Contrat de testabilite : la brique DOIT lire l'horloge via
    # `rate_limit.time.monotonic` (module `time` importe dans app/rate_limit.py).
    from app import rate_limit as rl

    rl.reset_rate_limit_state()
    clock = {"t": 1000.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: clock["t"])

    app = _build_short_window_app(limit=2, window_seconds=10.0)
    c = TestClient(app)
    headers = {"Fly-Client-IP": IP_A}

    assert c.get("/ping", headers=headers).status_code == 200
    assert c.get("/ping", headers=headers).status_code == 200
    # 3e dans la meme fenetre -> bloquee.
    assert c.get("/ping", headers=headers).status_code == 429

    # On avance le temps au-dela de la fenetre : les anciens timestamps expirent.
    clock["t"] += 11.0
    assert c.get("/ping", headers=headers).status_code != 429
    rl.reset_rate_limit_state()


def test_sliding_window_short_window_reopens_realtime():
    # Variante robustesse (sans mock) avec une fenetre TRES courte : tolere une
    # source de temps differente cote dev (monotonic/perf_counter) sans imposer
    # le nom interne. Reste falsifiable : apres la fenetre, l'IP repasse.
    import time

    from app.rate_limit import reset_rate_limit_state

    reset_rate_limit_state()
    app = _build_short_window_app(limit=2, window_seconds=0.2)
    c = TestClient(app)

    headers = {"Fly-Client-IP": IP_A}
    assert c.get("/ping", headers=headers).status_code == 200
    assert c.get("/ping", headers=headers).status_code == 200
    assert c.get("/ping", headers=headers).status_code == 429

    time.sleep(0.35)
    assert c.get("/ping", headers=headers).status_code != 429
    reset_rate_limit_state()


def test_short_window_buckets_per_ip():
    from app.rate_limit import reset_rate_limit_state

    reset_rate_limit_state()
    app = _build_short_window_app(limit=2, window_seconds=5.0)
    c = TestClient(app)

    for _ in range(3):
        c.get("/ping", headers={"Fly-Client-IP": IP_A})
    assert c.get("/ping", headers={"Fly-Client-IP": IP_A}).status_code == 429
    assert c.get("/ping", headers={"Fly-Client-IP": IP_B}).status_code != 429
    reset_rate_limit_state()


# ===========================================================================
# PHASE B — challenge adversarial : trous non couverts par la phase A.
# ===========================================================================


# --- Angle 1 : isolation inter-fichiers (SPEC §3.5 / lecon 9.7) ----------
# La SPEC §3.5 EXIGE la fixture de reset dans conftest.py (autouse, scope
# function). Or elle est locale a CE fichier. Un autre fichier de test qui
# sature un bucket /analyze (ou /feedback) SANS importer ce reset polluerait
# l'etat partage de module, faisant echouer un test suivant. Ce test simule
# exactement ce scenario inter-fichiers : on sature un bucket DEPUIS L'ETAT
# REEL (sans la fixture locale), puis on verifie qu'un conftest correct
# repartirait d'un etat vide. Falsifiable : si le reset n'est PAS dans
# conftest, rien ne garantit l'isolation hors de ce fichier.
def test_conftest_provides_global_rate_limit_reset():
    # Contrat SPEC §3.5 : le point de reset doit etre branche en autouse dans
    # conftest.py, pas seulement local a test_9_9_rate_limit.py. On le verifie
    # statiquement : la fixture conftest doit appeler reset_rate_limit_state.
    import os

    conftest_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "conftest.py"
    )
    with open(conftest_path, encoding="utf-8") as f:
        conftest_src = f.read()
    assert "reset_rate_limit_state" in conftest_src, (
        "SPEC 3.5 : la reinitialisation du rate-limit doit etre une fixture "
        "autouse dans conftest.py (isolation inter-fichiers, lecon 9.7), pas "
        "seulement locale a test_9_9_rate_limit.py"
    )


def test_cross_file_pollution_simulated():
    # Simule un AUTRE fichier de test qui saturerait /analyze sans la fixture
    # locale de reset. On sature directement l'etat de module, puis on verifie
    # qu'un nouveau client (comme dans un autre fichier sans fixture) serait
    # bloque -> demontre que SANS reset conftest, l'etat fuit entre fichiers.
    from app import rate_limit as rl

    rl.reset_rate_limit_state()
    app = _build_short_window_app(limit=2, window_seconds=60.0)
    c = TestClient(app)
    for _ in range(3):
        c.get("/ping", headers={"Fly-Client-IP": IP_A})
    # Etat de module pollue : un bucket scope/IP_A est sature.
    assert any(
        len(buf) >= 2 for buf in rl._buckets.values()
    ), "le bucket doit etre sature (etat partage de module)"
    # Sans reset conftest, ce bucket survivrait au test suivant d'un autre
    # fichier (meme scope reutilise via Depends global) -> pollution.
    rl.reset_rate_limit_state()
    assert all(len(buf) == 0 for buf in rl._buckets.values()) or not rl._buckets


def test_prod_app_state_leaks_without_conftest_reset(client, monkeypatch):
    # Preuve dynamique (pas juste statique) de la fuite inter-fichiers sur l'APP
    # REELLE : sans fixture autouse conftest, l'etat du bucket /feedback survit a
    # une saturation. On fige l'horloge pour que tous les hits restent dans la
    # meme fenetre, on sature /feedback depuis une IP via l'app de prod, puis on
    # constate que le bucket de module reste plein -> un autre fichier de test
    # sans reset heriterait de cet etat sature (faux rouge potentiel).
    from app import rate_limit as rl

    rl.reset_rate_limit_state()
    monkeypatch.setattr(rl.time, "monotonic", lambda: 555.0)

    ip = "203.0.113.200"
    for _ in range(FEEDBACK_LIMIT):
        client.post("/feedback", json={"rating": 3}, headers={"Fly-Client-IP": ip})

    # Le bucket /feedback de cette IP est plein (60 hits dans la fenetre figee).
    saturated = [len(buf) for buf in rl._buckets.values() if len(buf) >= FEEDBACK_LIMIT]
    assert saturated, "le bucket /feedback de prod doit etre sature"

    # SANS un reset autouse en conftest, ce bucket survit a la limite du test :
    # un fichier de test suivant qui re-poste /feedback depuis la meme IP (meme
    # client TestClient => meme request.client.host) verrait deja un 429.
    # On le prouve : la requete suivante, meme fenetre, est bloquee.
    blocked = client.post(
        "/feedback", json={"rating": 3}, headers={"Fly-Client-IP": ip}
    )
    assert blocked.status_code == 429, (
        "etat sature persistant : sans fixture autouse conftest (SPEC 3.5), la "
        "saturation d'un bucket fuit vers le test/fichier suivant"
    )
    # Nettoyage explicite ici car la fixture autouse n'est PAS globale.
    rl.reset_rate_limit_state()


# --- Angle 2 : frontiere exacte de la fenetre (off-by-one temporel) ------
def test_window_boundary_timestamp_exactly_at_window_is_purged(monkeypatch):
    # Un hit dont l'age vaut EXACTEMENT window_seconds doit-il etre dedans ou
    # dehors ? Contrat : purge si bucket[0] <= now - window. Donc a age ==
    # window, le hit expire (fenetre = ]t-w, t]). On verifie ce choix precis.
    from app import rate_limit as rl

    rl.reset_rate_limit_state()
    clock = {"t": 500.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: clock["t"])

    app = _build_short_window_app(limit=1, window_seconds=10.0)
    c = TestClient(app)
    headers = {"Fly-Client-IP": IP_A}

    assert c.get("/ping", headers=headers).status_code == 200  # t=500
    # Pile a la frontiere : age == window (t avance de exactement 10).
    clock["t"] = 510.0
    boundary = c.get("/ping", headers=headers)
    # Le 1er hit (t=500) a age 10 == window : expire -> requete passe.
    assert boundary.status_code == 200, (
        "a age == window le hit doit expirer (fenetre ]t-w, t]) ; sinon "
        "off-by-one temporel bloquant a la seconde pile"
    )
    rl.reset_rate_limit_state()


def test_retry_after_value_at_boundary_consistent(monkeypatch):
    # Au moment ou un hit vient juste d'entrer, Retry-After doit valoir ~window
    # (entier, borne a window) ; juste avant expiration, il doit tendre vers 1.
    from app import rate_limit as rl

    rl.reset_rate_limit_state()
    clock = {"t": 0.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: clock["t"])

    app = _build_short_window_app(limit=1, window_seconds=10.0)
    c = TestClient(app)
    headers = {"Fly-Client-IP": IP_A}

    c.get("/ping", headers=headers)  # hit a t=0
    # Juste apres : Retry-After ~ 10.
    clock["t"] = 0.001
    r = c.get("/ping", headers=headers)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) == 10

    # A 9.5s : le hit expire dans 0.5s -> ceil(0.5)=1.
    clock["t"] = 9.5
    r = c.get("/ping", headers=headers)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) == 1
    rl.reset_rate_limit_state()


# --- Angle 3 : purge effective des timestamps (fuite memoire) ------------
def test_slow_traffic_does_not_grow_deque(monkeypatch):
    # Une IP qui tape lentement mais longtemps (toujours sous le seuil) ne doit
    # PAS faire croitre sa deque sans borne : a chaque hit la purge doit evacuer
    # les timestamps hors fenetre. Sinon fuite memoire lente.
    from app import rate_limit as rl

    rl.reset_rate_limit_state()
    clock = {"t": 0.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: clock["t"])

    app = _build_short_window_app(limit=100, window_seconds=10.0)
    c = TestClient(app)
    headers = {"Fly-Client-IP": IP_A}

    # 200 hits espaces de 5s : a tout instant <= 2 hits dans la fenetre de 10s.
    for _ in range(200):
        c.get("/ping", headers=headers)
        clock["t"] += 5.0

    sizes = [len(buf) for buf in rl._buckets.values()]
    assert sizes, "le bucket doit exister"
    assert max(sizes) <= 3, (
        f"deque non purgee (taille {max(sizes)}) : fuite memoire, les "
        "timestamps hors fenetre ne sont pas evacues"
    )
    rl.reset_rate_limit_state()


# --- Angle 4 : XFF multi-hops, espaces, en-tete vide/malforme ------------
def test_xff_extra_spaces_around_first_hop(analyze_client):
    # "  198.51.100.5  , 10.0.0.1" : le 1er hop avec espaces parasites doit etre
    # strippe et servir de bucket. Une saturation doit aboutir a 429.
    last = None
    for _ in range(ANALYZE_LIMIT + 1):
        last = analyze_client.post(
            "/analyze",
            json=VALID_ANALYZE_BODY,
            headers={"X-Forwarded-For": "  198.51.100.5  , 10.0.0.1"},
        )
    assert last.status_code == 429
    # Meme IP sans espaces -> meme bucket -> deja bloquee.
    same = analyze_client.post(
        "/analyze",
        json=VALID_ANALYZE_BODY,
        headers={"X-Forwarded-For": "198.51.100.5, 10.0.0.1"},
    )
    assert same.status_code == 429, (
        "les espaces autour du 1er hop ne doivent pas creer un bucket distinct"
    )


def test_xff_empty_or_malformed_does_not_500(analyze_client):
    # En-tete XFF vide ou ne contenant qu'une virgule : pas de 500, repli propre.
    for bad in ["", "   ", ",", " , ", ",,,"]:
        resp = analyze_client.post(
            "/analyze",
            json=VALID_ANALYZE_BODY,
            headers={"X-Forwarded-For": bad},
        )
        assert resp.status_code != 500, f"XFF={bad!r} ne doit pas crasher"


def test_fly_client_ip_takes_priority_over_xff(analyze_client):
    # Fly-Client-IP prioritaire sur X-Forwarded-For (SPEC 2.3 ordre de repli).
    for _ in range(ANALYZE_LIMIT + 1):
        last = analyze_client.post(
            "/analyze",
            json=VALID_ANALYZE_BODY,
            headers={
                "Fly-Client-IP": IP_A,
                "X-Forwarded-For": "198.51.100.5, 10.0.0.1",
            },
        )
    assert last.status_code == 429
    # Une autre Fly-Client-IP, meme XFF : pas bloquee (c'est Fly-Client-IP qui
    # fait foi, pas le XFF).
    other = analyze_client.post(
        "/analyze",
        json=VALID_ANALYZE_BODY,
        headers={
            "Fly-Client-IP": IP_B,
            "X-Forwarded-For": "198.51.100.5, 10.0.0.1",
        },
    )
    assert other.status_code != 429


# --- Angle 5 : exactitude du compteur au seuil (pas d'off-by-one) --------
def test_exact_count_at_threshold_clock_mocked(monkeypatch):
    # Avec horloge figee (tous les hits dans la meme fenetre), EXACTEMENT
    # `limit` requetes passent et la (limit+1)e bloque. Verifie l'absence
    # d'off-by-one au seuil (>= limit, pas > limit).
    from app import rate_limit as rl

    rl.reset_rate_limit_state()
    monkeypatch.setattr(rl.time, "monotonic", lambda: 1234.0)

    limit = 10
    app = _build_short_window_app(limit=limit, window_seconds=60.0)
    c = TestClient(app)
    headers = {"Fly-Client-IP": IP_A}

    codes = [c.get("/ping", headers=headers).status_code for _ in range(limit + 1)]
    assert codes[:limit] == [200] * limit, "les `limit` premieres doivent passer"
    assert codes[limit] == 429, "la (limit+1)e doit etre bloquee (seuil exact)"
    rl.reset_rate_limit_state()


def test_limit_one_blocks_second_request(monkeypatch):
    # Cas limite minimal : limit=1. La 1re passe, la 2e (meme fenetre) bloque.
    from app import rate_limit as rl

    rl.reset_rate_limit_state()
    monkeypatch.setattr(rl.time, "monotonic", lambda: 42.0)
    app = _build_short_window_app(limit=1, window_seconds=60.0)
    c = TestClient(app)
    headers = {"Fly-Client-IP": IP_A}
    assert c.get("/ping", headers=headers).status_code == 200
    assert c.get("/ping", headers=headers).status_code == 429
    rl.reset_rate_limit_state()


# --- Angle bonus : isolation des scopes entre limiteurs ------------------
def test_distinct_scopes_do_not_share_counter(monkeypatch):
    # Deux limiteurs distincts (scopes differents) ne partagent pas le compteur
    # pour une meme IP : saturer le 1er ne doit pas bloquer le 2nd.
    from app import rate_limit as rl
    from app.rate_limit import rate_limiter

    rl.reset_rate_limit_state()
    monkeypatch.setattr(rl.time, "monotonic", lambda: 7.0)

    app = FastAPI()

    @app.get("/a")
    def a(_=Depends(rate_limiter(limit=2, window_seconds=60.0))):
        return {"ok": True}

    @app.get("/b")
    def b(_=Depends(rate_limiter(limit=2, window_seconds=60.0))):
        return {"ok": True}

    c = TestClient(app)
    headers = {"Fly-Client-IP": IP_A}
    for _ in range(3):
        c.get("/a", headers=headers)
    assert c.get("/a", headers=headers).status_code == 429
    assert c.get("/b", headers=headers).status_code == 200, (
        "un autre limiteur (scope distinct) ne doit pas heriter du blocage"
    )
    rl.reset_rate_limit_state()
