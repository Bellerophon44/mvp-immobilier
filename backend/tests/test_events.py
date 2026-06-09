"""Tests du critere 9.10 — instrumentation d'events first-party, RGPD-minimale.

Contrat : docs/specs/9.10-SPEC.md §4 (AC1 a AC15 backend ; AC16-AC20 = front,
verifies en revue, hors pytest).

Phase A (tests-first) : ROUGE LEGITIME attendu tant que la fonctionnalite
n'existe pas. Les echecs doivent porter sur l'ABSENCE de la brique :
- pas de classe `Event` dans `db.models` (ImportError) ;
- pas d'endpoint `POST /events` (404 au lieu de 201/422/429) ;
- pas de marqueur `_fallback` lu par `run_full_analysis`.
PAS sur des erreurs de syntaxe / collecte.

Garde-fous (lecons 9.7 / 9.9) :
- la table `events` est un etat partage persistant : vidage AVANT chaque test
  par la fixture autouse `_reset_events_table` de conftest.py (SPEC §3.8) ;
- les assertions de persistance filtrent sur une dimension UNIQUE au test
  (jamais un count() absolu accumule entre tests) ;
- les bornes d'enum sont testees aux valeurs EXACTES (valides ET invalides).
"""

import logging

import pytest
from fastapi.testclient import TestClient

IP_A = "203.0.113.41"
IP_B = "203.0.113.42"

EVENTS_LIMIT = 120

# Allowlist des noms d'events emissibles cote client (SPEC §3.2 ; `llm_fallback`
# est un event SERVEUR, teste via AC8). Mapping nom -> payload minimal valide.
VALID_EVENT_PAYLOADS = {
    "page_view": {"name": "page_view", "path": "/"},
    "methode_view": {"name": "methode_view", "path": "/methode"},
    "analysis_started": {"name": "analysis_started", "mode": "url"},
    "analysis_succeeded": {
        "name": "analysis_succeeded",
        "score_band": "60_79",
        "confidence": "Moyenne",
        "pillar_price_status": "aligne",
    },
    "analysis_failed": {"name": "analysis_failed", "reason": "url_unreachable"},
    "report_export": {"name": "report_export", "format": "pdf"},
    "district_refine": {
        "name": "district_refine",
        "from_scope": "ville",
        "to_scope": "quartier",
    },
    "address_entered": {"name": "address_entered", "address_entered": True},
}

# Ensemble exact des colonnes attendues (SPEC §3.1).
EXPECTED_EVENT_COLUMNS = {
    "id",
    "name",
    "mode",
    "score_band",
    "confidence",
    "pillar_price_status",
    "reason",
    "format",
    "from_scope",
    "to_scope",
    "address_entered",
    "path",
    "referrer_domain",
    "created_at",
}

FORBIDDEN_EVENT_COLUMNS = {
    "ip",
    "client_ip",
    "user_id",
    "session_id",
    "props",
    "url",
    "address",
    "comment",
    "raw_text",
    "referrer",
}

EXPECTED_REQUIREMENTS = {
    "fastapi",
    "uvicorn[standard]",
    "sqlalchemy",
    "requests",
    "beautifulsoup4",
    "openai",
    "numpy",
}


def _post_event(c, payload, ip=IP_A):
    return c.post("/events", json=payload, headers={"Fly-Client-IP": ip})


def _count_events(name=None, **filters):
    """Compte les lignes `events` du test courant (etat vide garanti en entree
    par la fixture autouse conftest). Filtre sur une dimension distinctive au
    test, jamais un count() absolu interpretatif accumule."""
    from sqlalchemy import text

    from db.session import engine

    clauses = []
    params = {}
    if name is not None:
        clauses.append("name = :name")
        params["name"] = name
    for k, v in filters.items():
        clauses.append(f"{k} = :{k}")
        params[k] = v
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT COUNT(*) FROM events{where}"), params
        ).scalar()


# ===========================================================================
# AC1 — Table `events` creee par create_all, sans migration.
# ===========================================================================
def test_ac1_events_table_created_by_create_all():
    from sqlalchemy import inspect

    from db.session import engine, init_db

    init_db()
    assert inspect(engine).has_table("events"), (
        "la table `events` doit etre creee par create_all au init_db (SPEC AC1)"
    )


def test_ac1_no_migrate_events_function():
    # YAGNI : pas de _migrate_events (schema complet d'emblee, SPEC §3.1 / AC1).
    import db.session as session_mod

    assert not hasattr(session_mod, "_migrate_events"), (
        "aucun _migrate_events attendu (schema complet d'emblee, AC1)"
    )


# ===========================================================================
# AC2 — POST /events 201 sur payload valide de chaque event de l'allowlist,
# avec persistance verifiee sur le bon `name`.
# ===========================================================================
@pytest.mark.parametrize("name", list(VALID_EVENT_PAYLOADS))
def test_ac2_valid_event_returns_201_and_persists(client, name):
    payload = VALID_EVENT_PAYLOADS[name]
    resp = _post_event(client, payload)
    assert resp.status_code == 201, f"{name} valide doit renvoyer 201"
    assert resp.json() == {"status": "ok"}
    # Etat vide en entree (fixture autouse) -> exactement 1 ligne de ce name.
    assert _count_events(name=name) == 1


def test_ac2_analysis_succeeded_persists_all_dimensions(client):
    payload = {
        "name": "analysis_succeeded",
        "score_band": "80plus",
        "confidence": "Élevée",
        "pillar_price_status": "sous",
    }
    resp = _post_event(client, payload)
    assert resp.status_code == 201
    # Filtre sur une dimension distinctive de CE test (score_band 80plus + sous).
    assert _count_events(
        name="analysis_succeeded",
        score_band="80plus",
        pillar_price_status="sous",
    ) == 1


# ===========================================================================
# AC3 — 422 sur name hors allowlist (aucune ligne inseree).
# ===========================================================================
@pytest.mark.parametrize(
    "bad_name", ["hack", "foo", "feedback_submitted", "repeat_session"]
)
def test_ac3_name_not_in_allowlist_rejected(client, bad_name):
    resp = _post_event(client, {"name": bad_name})
    assert resp.status_code == 422, f"name={bad_name!r} hors allowlist -> 422"
    assert _count_events(name=bad_name) == 0


# ===========================================================================
# AC4 — 422 sur valeur d'enum invalide, aux valeurs EXACTES (lecon 9.7).
# ===========================================================================
@pytest.mark.parametrize(
    "payload",
    [
        {"name": "analysis_started", "mode": "voice"},
        {"name": "report_export", "format": "xml"},
        {"name": "analysis_failed", "reason": "boom"},
        {"name": "district_refine", "from_scope": "galaxie", "to_scope": "ville"},
        {"name": "district_refine", "from_scope": "ville", "to_scope": "galaxie"},
        {"name": "analysis_succeeded", "score_band": "42",
         "confidence": "Moyenne", "pillar_price_status": "aligne"},
        {"name": "analysis_succeeded", "score_band": "60_79",
         "confidence": "Enorme", "pillar_price_status": "aligne"},
        {"name": "analysis_succeeded", "score_band": "60_79",
         "confidence": "Moyenne", "pillar_price_status": "cher"},
    ],
)
def test_ac4_invalid_enum_value_rejected(client, payload):
    resp = _post_event(client, payload)
    assert resp.status_code == 422, f"enum invalide doit etre rejetee : {payload}"


def test_ac4_no_row_inserted_on_invalid_enum(client):
    # Valeur d'enum invalide -> aucune ligne pour ce name distinctif.
    _post_event(client, {"name": "report_export", "format": "xml"})
    assert _count_events(name="report_export") == 0


# ===========================================================================
# AC5 — 422 / refus de tout champ inattendu (extra="forbid"), garde anti-PII.
# ===========================================================================
@pytest.mark.parametrize(
    "payload",
    [
        {"name": "page_view", "address": "3 rue de la Gare, Metz"},
        {"name": "analysis_started", "mode": "url", "url": "https://x.fr/annonce"},
        {"name": "page_view", "value": "texte libre d'annonce"},
        {"name": "page_view", "props": {"city": "Metz"}},
        {"name": "page_view", "raw_text": "appartement T3..."},
        {"name": "page_view", "ip": "8.8.8.8"},
        {"name": "page_view", "comment": "un avis"},
    ],
)
def test_ac5_extra_field_rejected(client, payload):
    resp = _post_event(client, payload)
    assert resp.status_code == 422, (
        f"champ non declare doit etre rejete (extra=forbid, anti-PII) : {payload}"
    )


def test_ac5_pii_field_not_persisted(client):
    # Tentative d'injection d'adresse via un champ libre : aucune ligne page_view.
    _post_event(client, {"name": "page_view", "address": "3 rue X"})
    assert _count_events(name="page_view") == 0


# ===========================================================================
# AC6 — address_entered est un booleen, jamais une chaine d'adresse.
# ===========================================================================
def test_ac6_address_entered_boolean_accepted(client):
    resp = _post_event(client, {"name": "address_entered", "address_entered": True})
    assert resp.status_code == 201
    assert _count_events(name="address_entered") == 1


def test_ac6_address_entered_false_accepted(client):
    resp = _post_event(client, {"name": "address_entered", "address_entered": False})
    assert resp.status_code == 201


def test_ac6_address_string_rejected(client):
    # Une chaine d'adresse en clair ne doit jamais entrer (bool strict).
    resp = _post_event(
        client, {"name": "address_entered", "address_entered": "3 rue X"}
    )
    assert resp.status_code == 422
    assert _count_events(name="address_entered") == 0


def test_ac6_address_entered_column_is_boolean():
    from sqlalchemy import Boolean

    from db.models import Event

    col = Event.__table__.columns["address_entered"]
    assert isinstance(col.type, Boolean), (
        "address_entered doit etre une colonne Boolean (jamais une chaine, AC6)"
    )


# ===========================================================================
# AC7 — Rate-limit /events actif : la 121e requete -> 429 (seuil 120/60s).
# La fixture autouse conftest `_reset_rate_limit_state` garantit l'isolation.
# ===========================================================================
def test_ac7_under_threshold_never_429(client):
    payload = VALID_EVENT_PAYLOADS["page_view"]
    for i in range(1, EVENTS_LIMIT + 1):
        resp = _post_event(client, payload, ip=IP_A)
        assert resp.status_code != 429, f"requete {i} ne doit pas etre 429"


def test_ac7_request_over_threshold_blocked(client):
    payload = VALID_EVENT_PAYLOADS["page_view"]
    for _ in range(EVENTS_LIMIT):
        _post_event(client, payload, ip=IP_A)
    resp = _post_event(client, payload, ip=IP_A)
    assert resp.status_code == 429, "la 121e requete /events doit etre 429"
    retry_after = int(resp.headers["Retry-After"])
    assert 1 <= retry_after <= 60


def test_ac7_buckets_per_ip_isolated(client):
    payload = VALID_EVENT_PAYLOADS["page_view"]
    for _ in range(EVENTS_LIMIT + 1):
        _post_event(client, payload, ip=IP_A)
    assert _post_event(client, payload, ip=IP_A).status_code == 429
    # Une IP differente n'herite pas du blocage.
    assert _post_event(client, payload, ip=IP_B).status_code != 429


# ===========================================================================
# AC8 — llm_fallback persiste quand le fallback est servi, SANS changer /analyze.
# ===========================================================================
@pytest.fixture()
def force_fallback(monkeypatch):
    """Force `analyze_semantic` (vue depuis app.analysis) a retourner le dict de
    fallback marque d'un drapeau interne `_fallback`. La SPEC §3.4 stipule que
    `run_full_analysis` lit ce marqueur (non expose dans AnalyzeResponse) et
    insere un Event(name="llm_fallback", reason="llm_fallback")."""
    import app.analysis as analysis_mod
    from app.llm_semantic import _FALLBACK

    def _fake_semantic(raw_text):
        result = dict(_FALLBACK)
        result["_fallback"] = True
        return result

    monkeypatch.setattr(analysis_mod, "analyze_semantic", _fake_semantic)


@pytest.fixture()
def no_fallback(monkeypatch):
    """`analyze_semantic` nominal (pas de marqueur de fallback) : aucune ligne
    llm_fallback ne doit etre inseree."""
    import app.analysis as analysis_mod

    def _fake_semantic(raw_text):
        return {
            "transparency_score": 70,
            "verdict": "Bonne",
            "risk_level": "Faible",
            "summary": "RAS.",
            "risk_summary": "RAS.",
            "questions": [],
            "negotiation_levers": [],
            "local_claims": [],
            "listing": {
                "city": None, "district": None, "property_type": None,
                "surface_m2": None, "price_total": None, "dpe": None,
                "construction_year": None, "floor": None, "has_elevator": None,
                "has_terrace": None, "has_balcony": None, "has_cellar": None,
                "parking": None, "bedrooms": None, "condo_fees": None,
            },
        }

    monkeypatch.setattr(analysis_mod, "analyze_semantic", _fake_semantic)


def test_ac8a_fallback_persists_llm_fallback_event(client, force_fallback):
    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement T3 a Metz, 70 m2."},
        headers={"Fly-Client-IP": IP_A},
    )
    assert resp.status_code == 200
    # Exactement une ligne llm_fallback avec reason=llm_fallback (etat vide entree).
    assert _count_events(name="llm_fallback", reason="llm_fallback") == 1


def test_ac8b_analyze_response_gains_no_key(client, force_fallback):
    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement T3 a Metz, 70 m2."},
        headers={"Fly-Client-IP": IP_A},
    )
    assert resp.status_code == 200
    keys = set(resp.json().keys())
    allowed = {
        "global_score", "verdict", "confidence", "pillars", "actions",
        "local_context",
    }
    assert keys <= allowed, (
        f"le corps /analyze ne doit gagner AUCUNE cle interne : {keys - allowed}"
    )
    assert "_fallback" not in keys
    assert "degraded" not in keys


def test_ac8_no_fallback_inserts_nothing(client, no_fallback):
    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement T3 a Metz, 70 m2."},
        headers={"Fly-Client-IP": IP_A},
    )
    assert resp.status_code == 200
    assert _count_events(name="llm_fallback") == 0


# ===========================================================================
# AC9 — Le logger `events` ne fuit aucune dimension sensible.
# ===========================================================================
def test_ac9_logger_does_not_leak_referrer_or_path(client, caplog):
    with caplog.at_level(logging.DEBUG):
        _post_event(
            client,
            {"name": "page_view", "path": "/methode", "referrer_domain": "exemple.fr"},
        )
        _post_event(
            client,
            {"name": "analysis_succeeded", "score_band": "lt40",
             "confidence": "Faible", "pillar_price_status": "fort_sur"},
        )
    assert "exemple.fr" not in caplog.text, "le referrer_domain ne doit jamais etre logge"
    assert IP_A not in caplog.text, "l'IP ne doit jamais etre loggee"


# ===========================================================================
# AC10 — referrer_domain borne au hostname (jamais path/query).
# ===========================================================================
def test_ac10_referrer_hostname_accepted(client):
    resp = _post_event(
        client, {"name": "page_view", "path": "/", "referrer_domain": "google.com"}
    )
    assert resp.status_code == 201


@pytest.mark.parametrize(
    "bad_referrer",
    [
        "google.com/search?q=x",
        "evil.com/path?token=x",
        "exemple.fr/page",
        "site.fr?utm=abc",
    ],
)
def test_ac10_referrer_with_path_or_query_rejected(client, bad_referrer):
    resp = _post_event(
        client,
        {"name": "page_view", "path": "/", "referrer_domain": bad_referrer},
    )
    assert resp.status_code == 422, (
        f"un referrer_domain non-hostname doit etre rejete : {bad_referrer!r}"
    )


# ===========================================================================
# AC11 — path borne a l'allowlist {/, /methode}.
# ===========================================================================
def test_ac11_path_root_accepted(client):
    assert _post_event(client, {"name": "page_view", "path": "/"}).status_code == 201


def test_ac11_path_methode_accepted(client):
    assert _post_event(
        client, {"name": "page_view", "path": "/methode"}
    ).status_code == 201


@pytest.mark.parametrize(
    "bad_path", ["/admin", "/secret", "https://x.fr/bien", "/methode/sub"]
)
def test_ac11_path_outside_allowlist_rejected(client, bad_path):
    resp = _post_event(client, {"name": "page_view", "path": bad_path})
    assert resp.status_code == 422, f"path={bad_path!r} hors allowlist -> 422"
    assert _count_events(path=bad_path) == 0


# ===========================================================================
# AC12 — Aucune colonne IP / identifiant / props dans Event.__table__.
# ===========================================================================
def test_ac12_event_columns_exactly_expected():
    from db.models import Event

    columns = {c.name for c in Event.__table__.columns}
    assert columns == EXPECTED_EVENT_COLUMNS, (
        f"colonnes inattendues : {columns ^ EXPECTED_EVENT_COLUMNS}"
    )


def test_ac12_no_pii_columns():
    from db.models import Event

    columns = {c.name for c in Event.__table__.columns}
    assert not (columns & FORBIDDEN_EVENT_COLUMNS), (
        f"colonnes PII interdites presentes : {columns & FORBIDDEN_EVENT_COLUMNS}"
    )


def test_ac12_sql_schema_has_no_pii(client):
    from sqlalchemy import text

    from db.session import engine

    with engine.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(events)"))}
    assert cols == EXPECTED_EVENT_COLUMNS
    assert not (cols & FORBIDDEN_EVENT_COLUMNS)


# ===========================================================================
# AC13 — Aucune nouvelle dependance (requirements.txt = 7 lignes, memes paquets).
# ===========================================================================
def test_ac13_requirements_unchanged():
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

    assert {_name(ln) for ln in lines} == EXPECTED_REQUIREMENTS


# ===========================================================================
# AC14 — Isolation events entre tests : etat vide en entree (fixture autouse).
# Deux tests inserent N lignes ; chacun repart de 0 grace au reset conftest.
# ===========================================================================
def test_ac14_conftest_provides_events_reset():
    # Contrat SPEC §3.8 : la table `events` doit etre videe par une fixture
    # autouse en conftest.py (pas locale a ce fichier).
    import os

    conftest_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "conftest.py"
    )
    with open(conftest_path, encoding="utf-8") as f:
        src = f.read()
    assert "DELETE FROM events" in src or "events" in src and "delete" in src.lower(), (
        "SPEC 3.8 : la reinitialisation de la table events doit etre une fixture "
        "autouse en conftest.py (isolation, lecons 9.7/9.9)"
    )


def test_ac14_isolation_first_inserts_many(client):
    for _ in range(5):
        _post_event(client, VALID_EVENT_PAYLOADS["page_view"])
    assert _count_events(name="page_view") == 5


def test_ac14_isolation_second_starts_empty(client):
    # Si la table n'etait pas videe entre tests, le test precedent (5 page_view)
    # ferait echouer cette assertion d'etat vide.
    assert _count_events(name="page_view") == 0
    _post_event(client, VALID_EVENT_PAYLOADS["page_view"])
    assert _count_events(name="page_view") == 1


# ===========================================================================
# AC15 — Contrat /analyze ({} -> 400) et /feedback ({"rating":3} -> 201, 60/min)
# inchanges par l'introduction de /events.
# ===========================================================================
def test_ac15_analyze_empty_body_still_400(client):
    resp = client.post("/analyze", json={}, headers={"Fly-Client-IP": IP_A})
    assert resp.status_code == 400


def test_ac15_feedback_still_201(client):
    resp = client.post(
        "/feedback", json={"rating": 3}, headers={"Fly-Client-IP": IP_A}
    )
    assert resp.status_code == 201
    assert resp.json() == {"status": "ok"}


def test_ac15_feedback_still_60_per_min(client):
    # /feedback reste a 60/min : la 61e requete depuis une IP fixe -> 429,
    # les 60 premieres passent (preuve que /events n'a pas modifie ce seuil).
    ip = "203.0.113.77"
    statuses = [
        client.post("/feedback", json={"rating": 3}, headers={"Fly-Client-IP": ip}).status_code
        for _ in range(61)
    ]
    assert all(s != 429 for s in statuses[:60])
    assert statuses[60] == 429
