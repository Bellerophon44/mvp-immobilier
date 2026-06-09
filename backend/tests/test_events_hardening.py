"""Durcissement adversarial (phase B challenge) du critere 9.10.

Ces tests complotent CONTRE l'implementation : ils ferment les angles morts
laisses par `test_events.py` (assertions tautologiques, chemins reels non
couverts, garde-fous anti-PII partiels), conformement a la SPEC 9.10 §3.4 / §6
et aux lecons 9.7 / 9.9 (faux-vert, etat partage).

Angles attaques :
- AC8(a/b) : le fallback est teste ici via le CHEMIN REEL (OpenAI qui leve), pas
  seulement un monkeypatch de `analyze_semantic` ; et on verifie que
  `run_full_analysis` lui-meme ne FUIT PAS `_fallback` (independamment du filtre
  `response_model=AnalyzeResponse` qui masquerait un oubli du dev).
- AC9 : le logger `events` doit emettre le `name` (preuve de non-vacuite) ET ne
  fuiter AUCUNE valeur de dimension fermee sensible.
- AC10 : garde-fou serveur referrer_domain durci (userinfo `@`, fragment `#`,
  saut de ligne) au-dela du strict `/` et `?` de l'AC.
- AC8 best-effort : une erreur DB sur l'insert llm_fallback ne fait pas echouer
  /analyze.
"""

import logging

import pytest

IP_A = "203.0.113.41"


# ===========================================================================
# AC8 — fallback teste sur le CHEMIN REEL (OpenAI leve), pas via monkeypatch
# de analyze_semantic. On force `client.chat.completions.create` a lever pour
# exercer le `except` de llm_semantic qui pose le marqueur `_fallback`.
# ===========================================================================
@pytest.fixture()
def openai_raises(monkeypatch):
    """Simule une panne OpenAI au niveau le plus bas (le client SDK), pour que
    le marqueur `_fallback` soit pose par le VRAI chemin de
    `llm_semantic.analyze_semantic`, et non injecte par le test."""
    import app.llm_semantic as llm

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated OpenAI outage (hardening)")

    monkeypatch.setattr(llm.client.chat.completions, "create", _boom)
    # Le cache pourrait servir un resultat nominal d'un test anterieur : on le
    # vide pour garantir que l'appel passe par le client (et donc par _boom).
    llm._CACHE.clear()


def test_real_fallback_path_persists_event_and_keeps_contract(client, openai_raises):
    # Texte unique (jamais en cache) pour forcer l'appel client -> except -> fallback.
    resp = client.post(
        "/analyze",
        json={"raw_text": "annonce adversariale bout-en-bout fallback reel unique 9.10"},
        headers={"Fly-Client-IP": IP_A},
    )
    assert resp.status_code == 200, "le fallback LLM doit rendre un 200 normal cote /analyze"

    # AC8a : exactement une ligne llm_fallback persistee via le chemin reel.
    from sqlalchemy import text

    from db.session import engine

    with engine.connect() as conn:
        n = conn.execute(
            text(
                "SELECT COUNT(*) FROM events "
                "WHERE name = 'llm_fallback' AND reason = 'llm_fallback'"
            )
        ).scalar()
    assert n == 1, "le fallback REEL doit persister une ligne llm_fallback (AC8a)"

    # AC8b : le corps /analyze ne gagne AUCUNE cle interne, meme sur fallback reel.
    keys = set(resp.json().keys())
    allowed = {
        "global_score", "verdict", "confidence", "pillars", "actions",
        "local_context",
    }
    assert keys <= allowed, f"cle interne fuitee dans /analyze : {keys - allowed}"
    assert "_fallback" not in keys
    assert "degraded" not in keys


def test_run_full_analysis_does_not_return_fallback_marker(openai_raises):
    # Garde-fou anti-tautologie : le test AC8b officiel passe APRES le filtre
    # `response_model=AnalyzeResponse` (qui supprimerait silencieusement une cle
    # _fallback oubliee). Ici on appelle run_full_analysis DIRECTEMENT : si le dev
    # oubliait de retirer le marqueur du dict retourne, ce test echouerait, lui.
    from app.analysis import run_full_analysis

    res = run_full_analysis("annonce directe sans response_model unique 9.10 xyz")
    assert "_fallback" not in res, (
        "run_full_analysis NE doit PAS propager le marqueur interne _fallback "
        "(le filtre response_model ne doit pas etre le seul garde-fou) — SPEC §3.4"
    )
    assert "degraded" not in res


def test_no_fallback_marker_on_llm_success(monkeypatch):
    # Le marqueur _fallback ne doit JAMAIS apparaitre en cas de succes LLM
    # (sinon llm_fallback serait compte a tort sur chaque analyse nominale).
    import app.llm_semantic as llm

    class _Msg:
        content = (
            '{"transparency_score":70,"verdict":"Bonne","risk_level":"Faible",'
            '"summary":"ok","risk_summary":"ok","questions":[],'
            '"negotiation_levers":[],"local_claims":[],"listing":{}}'
        )

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    monkeypatch.setattr(
        llm.client.chat.completions, "create", lambda *a, **k: _Resp()
    )
    llm._CACHE.clear()
    res = llm.analyze_semantic("succes nominal unique hardening 9.10 abc")
    assert "_fallback" not in res, (
        "aucun marqueur _fallback en cas de succes LLM (sinon faux positif AC8)"
    )


def test_record_llm_fallback_event_swallows_commit_error(monkeypatch):
    # AC8 best-effort (SPEC §3.4), scenario REALISTE : la panne DB de SQLAlchemy
    # se manifeste au flush/commit (table absente, disque plein, verrou), PAS a
    # l'instanciation de la session. On fait lever `commit()` et on verifie que
    # _record_llm_fallback_event AVALE l'erreur (ne remonte rien -> /analyze 200).
    import db.session as db_session
    from app.analysis import _record_llm_fallback_event

    real_session_factory = db_session.SessionLocal

    class _CommitBoom:
        def __init__(self):
            self._s = real_session_factory()

        def add(self, *a, **k):
            return self._s.add(*a, **k)

        def commit(self):
            raise RuntimeError("commit DB indisponible (hardening realiste)")

        def close(self):
            return self._s.close()

    monkeypatch.setattr(db_session, "SessionLocal", _CommitBoom)

    # Ne doit RIEN lever malgre le commit casse (try/except interne best-effort).
    _record_llm_fallback_event()


def test_record_llm_fallback_event_swallows_session_open_error(monkeypatch):
    # Durci en 9.10 : `db = SessionLocal()` est desormais DANS le try de
    # _record_llm_fallback_event (analysis.py) -> meme une panne a l'OUVERTURE
    # de session est avalee (best-effort strict). Ne doit rien lever.
    import db.session as db_session
    from app.analysis import _record_llm_fallback_event

    def _broken_session():
        raise RuntimeError("ouverture de session impossible")

    monkeypatch.setattr(db_session, "SessionLocal", _broken_session)
    _record_llm_fallback_event()  # devrait ne rien lever, best-effort strict


# ===========================================================================
# AC9 — durcissement logger : il EMET le name (non-vacuite) et ne fuit AUCUNE
# valeur de dimension fermee sensible (pas seulement referrer/IP).
# ===========================================================================
def test_ac9_logger_emits_name_but_no_dimension_value(client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post(
            "/events",
            json={
                "name": "analysis_succeeded",
                "score_band": "lt40",
                "confidence": "Faible",
                "pillar_price_status": "fort_sur",
            },
            headers={"Fly-Client-IP": IP_A},
        )
    events_logs = "\n".join(
        r.getMessage() for r in caplog.records if r.name == "events"
    )
    # Non-vacuite : le name DOIT etre journalise (preuve que le logger sert).
    assert "analysis_succeeded" in events_logs, (
        "le logger events doit au moins emettre le name (sinon assertion vide)"
    )
    # Aucune valeur de dimension fermee ne doit fuiter dans le log events.
    for leaky in ("lt40", "fort_sur"):
        assert leaky not in events_logs, (
            f"la valeur de dimension {leaky!r} ne doit pas etre journalisee (AC9)"
        )


def test_ac9_logger_never_emits_referrer_value(client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post(
            "/events",
            json={"name": "page_view", "path": "/methode",
                  "referrer_domain": "tres-sensible-domaine.example"},
            headers={"Fly-Client-IP": IP_A},
        )
    events_logs = "\n".join(
        r.getMessage() for r in caplog.records if r.name == "events"
    )
    assert "tres-sensible-domaine.example" not in events_logs
    # Mais la PRESENCE d'un referrer peut etre signalee par un booleen.
    assert "page_view" in events_logs


# ===========================================================================
# AC4 — accents contractuels de `confidence` (leçon 9.7 : valeur EXACTE).
# Le domaine est {Élevée, Moyenne, Faible} AVEC accents (libelles reels FR de
# AnalyzeResponse, SPEC §3.1). La forme desaccentuee ne doit JAMAIS passer.
# ===========================================================================
@pytest.mark.parametrize("value", ["Élevée", "Moyenne", "Faible"])
def test_ac4_confidence_accented_accepted(client, value):
    resp = client.post(
        "/events",
        json={"name": "analysis_succeeded", "confidence": value},
        headers={"Fly-Client-IP": IP_A},
    )
    assert resp.status_code == 201, f"{value!r} (avec accents) doit etre accepte"


@pytest.mark.parametrize("value", ["Elevee", "elevee", "ELEVEE", "Elevée", "Moyene"])
def test_ac4_confidence_unaccented_or_misspelled_rejected(client, value):
    resp = client.post(
        "/events",
        json={"name": "analysis_succeeded", "confidence": value},
        headers={"Fly-Client-IP": IP_A},
    )
    assert resp.status_code == 422, (
        f"{value!r} (sans accent / mal orthographie) doit etre rejete (borne exacte)"
    )


# ===========================================================================
# AC10 — garde-fou serveur referrer_domain : « hostname seul » (§3.1). Durci en
# 9.10 par une whitelist positive `[A-Za-z0-9.-]+` (validator `_hostname_only`)
# qui rejette path/query MAIS aussi userinfo (`user:pass@`), fragment (`#`),
# port (`:`) et saut de ligne (anti log-injection / fuite de credential).
@pytest.mark.parametrize(
    "bad_referrer",
    [
        "user:secret-token@google.com",  # credentials/PII dans l'userinfo
        "google.com#fragment",           # fragment, pas un hostname
        "evil.com\nInjected: log",       # saut de ligne (injection de log)
    ],
)
def test_ac10_referrer_non_hostname_residual_risk(client, bad_referrer):
    resp = client.post(
        "/events",
        json={"name": "page_view", "path": "/", "referrer_domain": bad_referrer},
        headers={"Fly-Client-IP": IP_A},
    )
    assert resp.status_code == 422, (
        "ideal : un referrer_domain non-hostname (userinfo/fragment/newline) "
        f"devrait etre rejete par le garde-fou serveur : {bad_referrer!r}"
    )
