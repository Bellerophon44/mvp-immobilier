"""Tests-first (phase A) — Contexte local v2, volet C endpoint POST /travel-times
+ sonde statique api.ts. AC couverts : AC18-AC22, AC27-AC28, AC30.
Spec : docs/specs/contexte-local-v2-SPEC.md §3.C.3 / §4.2 / §4.3 / §5.

ETAT ATTENDU EN PHASE A : ROUGE — l'endpoint POST /travel-times n'existe pas
(404/405), les types TravelTimes* et la fonction fetchTravelTimes ne sont pas dans
api.ts. Les tests echouent donc legitimement.

REGLES :
- AUCUN appel reseau reel. `geocode_address` est PATCHE (vu depuis app.main),
  `compute_travel_times` est PATCHE (vu depuis app.main) pour ne jamais sortir.
- Bornes EXACTES du rate-limit (lecon 9.7) : la 30e passe, la 31e -> 429.
- RGPD : aucune coordonnee dans la reponse ; aucune ecriture DB.

HOOK D'INJECTION SUPPOSEE (a signaler au developpeur) : on suppose que le handler
`/travel-times` (app.main) appelle `geocode_address` et `compute_travel_times`
importes dans app.main (patchables via monkeypatch.setattr(main, ...)). Si le
handler les importe localement (import dans la fonction), il faudra patcher au
module d'origine (app.geocode / app.routing) — le helper de patch est centralise.
"""

import re
from pathlib import Path

import pytest

import app.main as main


TEST_LAT = 49.1150
TEST_LON = 6.1650

POI_IDS = {"cathedrale", "gare", "pompidou", "a31"}


def _fake_geo(addr, city_hint="Metz"):
    return {
        "lat": TEST_LAT, "lon": TEST_LON, "score": 0.9, "label": "Adresse Test",
        "city": "Metz", "citycode": "57463", "postcode": "57000",
    }


def _fake_routing_ok(origin, destinations, mode, client=None):
    """Renvoie un temps reel pour chaque POI demande (resultats mockes)."""
    return {
        p: {"mode": mode, "distance_m": 600, "duration_s": 480}
        for p in destinations
    }


@pytest.fixture()
def patch_endpoint(monkeypatch):
    """Patche geocode_address ET compute_travel_times tels que vus depuis app.main.
    raising=False : tant que app.main n'importe pas encore ces symboles (phase
    tests-first), le setattr ne casse pas la collecte ; les tests echoueront sur
    l'absence de l'endpoint (404)."""
    monkeypatch.setattr(main, "geocode_address", _fake_geo, raising=False)
    monkeypatch.setattr(main, "compute_travel_times", _fake_routing_ok, raising=False)


def _coord_key_found(obj):
    coord_keys = {"lat", "lon", "latitude", "longitude"}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in coord_keys:
                return k
            f = _coord_key_found(v)
            if f:
                return f
    elif isinstance(obj, list):
        for v in obj:
            f = _coord_key_found(v)
            if f:
                return f
    return None


# ===========================================================================
# AC18 — succes : status ok, results non vide, poi_id dans l'ensemble attendu
# ===========================================================================
def test_ac18_success(client, patch_endpoint):
    """AC18 : POST /travel-times avec geocode patche (coords connues) et routing
    mocke -> status='ok', results[] non vide, chaque result porte poi_id ∈
    {cathedrale, gare, pompidou, a31}."""
    resp = client.post(
        "/travel-times",
        json={"address": "3 Rue Test Metz", "mode": "WALK"},
        headers={"Fly-Client-IP": "198.51.100.10"},
    )
    assert resp.status_code == 200, f"AC18 : 200 attendu, recu {resp.status_code} {resp.text}"
    body = resp.json()
    assert body.get("status") == "ok", f"AC18 : status 'ok' attendu, recu {body!r}"
    results = body.get("results") or []
    assert results, "AC18 : results[] non vide attendu"
    for r in results:
        assert r.get("poi_id") in POI_IDS, (
            f"AC18 : poi_id attendu dans {POI_IDS}, recu {r.get('poi_id')!r}"
        )


# ===========================================================================
# AC19 — indisponible adresse : 200 status indisponible reason adresse
# ===========================================================================
def test_ac19_unavailable_address(client, monkeypatch):
    """AC19 : geocode_address patche -> None -> HTTP 200
    {'status':'indisponible','reason':'adresse'} (pas de 500)."""
    monkeypatch.setattr(main, "geocode_address", lambda addr, city_hint="Metz": None,
                        raising=False)
    monkeypatch.setattr(main, "compute_travel_times", _fake_routing_ok, raising=False)

    resp = client.post(
        "/travel-times",
        json={"address": "adresse introuvable", "mode": "DRIVE"},
        headers={"Fly-Client-IP": "198.51.100.11"},
    )
    assert resp.status_code == 200, (
        f"AC19 : 200 attendu meme en indisponible, recu {resp.status_code}"
    )
    body = resp.json()
    assert body.get("status") == "indisponible" and body.get("reason") == "adresse", (
        f"AC19 : {{status:indisponible, reason:adresse}} attendu, recu {body!r}"
    )


# ===========================================================================
# AC20 — validation : address vide/absente, mode hors enum, champ extra -> 422
# ===========================================================================
def test_ac20_missing_address_422(client, patch_endpoint):
    """AC20 : body sans `address` -> 422 (Field min_length=1 requis)."""
    resp = client.post("/travel-times", json={"mode": "WALK"},
                       headers={"Fly-Client-IP": "198.51.100.12"})
    assert resp.status_code == 422, f"AC20 : 422 attendu sans address, recu {resp.status_code}"


def test_ac20_empty_address_422(client, patch_endpoint):
    """AC20 : address='' -> 422 (min_length=1)."""
    resp = client.post("/travel-times", json={"address": "", "mode": "WALK"},
                       headers={"Fly-Client-IP": "198.51.100.13"})
    assert resp.status_code == 422, f"AC20 : 422 attendu sur address vide, recu {resp.status_code}"


def test_ac20_invalid_mode_422(client, patch_endpoint):
    """AC20 : mode hors enum {WALK,DRIVE,BICYCLE,TRANSIT} -> 422."""
    resp = client.post("/travel-times", json={"address": "3 Rue Test", "mode": "FLY"},
                       headers={"Fly-Client-IP": "198.51.100.14"})
    assert resp.status_code == 422, f"AC20 : 422 attendu sur mode invalide, recu {resp.status_code}"


def test_ac20_extra_field_422(client, patch_endpoint):
    """AC20 : champ extra -> 422 (model_config extra='forbid')."""
    resp = client.post(
        "/travel-times",
        json={"address": "3 Rue Test", "mode": "WALK", "lat": 49.1},
        headers={"Fly-Client-IP": "198.51.100.15"},
    )
    assert resp.status_code == 422, (
        f"AC20 : 422 attendu sur champ extra (extra='forbid'), recu {resp.status_code}"
    )


# ===========================================================================
# AC21 — rate-limit : 30e passe, 31e -> 429 + Retry-After (bornes exactes)
# ===========================================================================
def test_ac21_rate_limit_30th_passes_31st_429(client, patch_endpoint):
    """AC21 : sur une meme IP, les 30 premieres requetes passent (pas 429) et la 31e
    renvoie 429 avec en-tete Retry-After. Bornes EXACTES (lecon 9.7). Le reset
    autouse du rate-limit (conftest) garantit un bucket vierge en debut de test."""
    ip = {"Fly-Client-IP": "198.51.100.30"}
    body = {"address": "3 Rue Test Metz", "mode": "WALK"}

    for i in range(1, 31):
        r = client.post("/travel-times", json=body, headers=ip)
        assert r.status_code != 429, (
            f"AC21 : la requete #{i} ne doit pas etre limitee (30e doit passer), "
            f"recu {r.status_code}"
        )

    r31 = client.post("/travel-times", json=body, headers=ip)
    assert r31.status_code == 429, (
        f"AC21 : la 31e requete doit etre limitee (429), recu {r31.status_code}"
    )
    assert "Retry-After" in r31.headers, (
        f"AC21 : en-tete Retry-After attendu sur 429, recu {dict(r31.headers)}"
    )


# ===========================================================================
# AC22 — sans LLM ni DB : sonde statique sur le corps du handler
# ===========================================================================
def test_ac22_handler_no_llm_no_db():
    """AC22 : le corps du handler /travel-times n'appelle ni analyze_semantic ni
    n'ouvre de session DB (sonde statique sur la fonction source). On localise la
    fonction par son chemin de route et on inspecte son code source."""
    import inspect

    src = Path(__file__).resolve().parents[1] / "app" / "main.py"
    content = src.read_text(encoding="utf-8")
    assert "/travel-times" in content, (
        "AC22 : la route POST /travel-times doit etre declaree dans app.main"
    )

    # Extraction du corps de la fonction decoree par @app.post("/travel-times").
    lines = content.splitlines()
    start = None
    for i, line in enumerate(lines):
        if '"/travel-times"' in line or "'/travel-times'" in line:
            start = i
            break
    assert start is not None, "AC22 : decorateur de route /travel-times introuvable"

    # Corps = du decorateur jusqu'au prochain decorateur @app. de meme niveau.
    body_lines = []
    for line in lines[start:]:
        if body_lines and line.startswith("@app."):
            break
        body_lines.append(line)
    body = "\n".join(body_lines[1:])  # saute la ligne du decorateur
    for forbidden in ("analyze_semantic", "SessionLocal"):
        assert forbidden not in body, (
            f"AC22 : le handler /travel-times ne doit pas reference {forbidden!r} "
            f"(sans LLM ni DB)"
        )


# ===========================================================================
# AC27 — RGPD reponse : aucune coordonnee (lat/lon) dans la reponse
# ===========================================================================
def test_ac27_response_has_no_coordinates(client, patch_endpoint):
    """AC27 : la reponse POST /travel-times ne contient aucune lat/lon ; seuls
    poi_id, labels, valeurs textuelles, durees/distances entieres. Sonde recursive."""
    resp = client.post(
        "/travel-times",
        json={"address": "3 Rue Test Metz", "mode": "WALK"},
        headers={"Fly-Client-IP": "198.51.100.27"},
    )
    assert resp.status_code == 200
    found = _coord_key_found(resp.json())
    assert found is None, (
        f"AC27 : aucune coordonnee dans la reponse /travel-times, trouvee {found!r}"
    )


# ===========================================================================
# AC28 — RGPD DB : aucune ecriture en base, aucune adresse persistee
# ===========================================================================
def test_ac28_no_db_writes(client, patch_endpoint):
    """AC28 : POST /travel-times n'ecrit aucune ligne en base (count de toutes les
    tables inchange avant/apres) et ne persiste aucune adresse/coordonnee."""
    from db.session import engine
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    tables = insp.get_table_names()

    def _counts():
        c = {}
        for t in tables:
            with engine.begin() as conn:
                c[t] = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
        return c

    before = _counts()
    secret = "13 Rue Tres Privee 57000 Metz"
    resp = client.post(
        "/travel-times",
        json={"address": secret, "mode": "DRIVE"},
        headers={"Fly-Client-IP": "198.51.100.28"},
    )
    assert resp.status_code == 200
    after = _counts()
    assert before == after, (
        f"AC28 : aucune ecriture DB attendue ; counts avant={before} apres={after}"
    )

    # Aucune table ne doit contenir l'adresse saisie.
    for t in tables:
        with engine.begin() as conn:
            rows = conn.execute(text(f'SELECT * FROM "{t}"')).fetchall()
        blob = "\n".join("|".join("" if v is None else str(v) for v in r) for r in rows)
        assert "Tres Privee" not in blob, (
            f"AC28 : la table {t!r} ne doit pas persister l'adresse saisie (RGPD)"
        )


# ===========================================================================
# AC30 — sonde statique api.ts : LocalFact + TravelTimes* + fetchTravelTimes
# ===========================================================================
def _api_ts():
    p = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "api.ts"
    assert p.exists(), f"AC30 : api.ts introuvable a {p}"
    return p.read_text(encoding="utf-8")


def test_ac30_api_ts_declares_local_fact_optional_fields():
    """AC30 : api.ts declare l'interface LocalFact avec les champs optionnels
    mode/duration_s/distance_m/estimated/poi_id. Rouge tant que le front n'est pas
    mis a jour (garde-fou 'pas de schema sans MAJ api.ts')."""
    content = _api_ts()
    assert re.search(r"interface\s+LocalFact\b", content), (
        "AC30 : interface LocalFact attendue dans api.ts"
    )
    for field in ("mode?", "duration_s?", "distance_m?", "estimated?", "poi_id?"):
        assert field in content, (
            f"AC30 : champ optionnel {field!r} attendu dans api.ts (LocalFact)"
        )


def test_ac30_api_ts_declares_travel_times_types_and_fn():
    """AC30 : api.ts declare les types TravelTimes* (Request/Response/Result) ET la
    fonction fetchTravelTimes (POST /travel-times)."""
    content = _api_ts()
    assert re.search(r"interface\s+TravelTimesResponse\b", content), (
        "AC30 : interface TravelTimesResponse attendue dans api.ts"
    )
    assert re.search(r"interface\s+TravelTime", content), (
        "AC30 : au moins un type TravelTime*/TravelTimes* attendu dans api.ts"
    )
    assert "fetchTravelTimes" in content, (
        "AC30 : fonction fetchTravelTimes attendue dans api.ts"
    )
