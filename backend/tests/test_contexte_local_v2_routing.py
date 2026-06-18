"""Tests-first (phase A) — Contexte local v2, volet C (module routing + aiguillage
analyse + etiquetage honnete + RGPD reponse /analyze + retro-compat facts +
invariants non-score/anti-patterns).
AC couverts : AC7-AC17, AC23-AC26, AC29, AC41-AC42.
Spec : docs/specs/contexte-local-v2-SPEC.md §3.C / §4 / §5 / §7.

ETAT ATTENDU EN PHASE A : ROUGE — `app/routing.py` (compute_travel_times,
reset_routing_cache), l'aiguillage par defaut dans local_context_from_coords, et
les nouveaux champs de fact n'existent pas. Imports des points d'accroche absents
LOCAUX aux tests pour ne pas casser la collecte du module.

REGLES DE FALSIFIABILITE (lecons 9.10 / BAN-egress) :
- AUCUN appel reseau reel. Le client Google est MOCKE et injecte via `client=`.
- Le repli reseau (AC9) / le /analyze robuste (AC17) font LEVER la VRAIE dependance
  (client mocke qui raise ; monkeypatch de compute_travel_times qui raise), pas un
  stub qui renvoie le repli.
- AC26 (pas de lat/lon) : sonde RECURSIVE sur le dict renvoye par run_full_analysis
  DIRECTEMENT (hors response_model), en plus du corps HTTP.

HOOK D'INJECTION SUPPOSEE (a signaler au developpeur) : la signature publique
`compute_travel_times(origin, destinations, mode, client=None)` est fixee par la
spec §3 C.1. L'INTERFACE du client mocke n'est PAS fixee par la spec. On suppose
que le module appelle UNE methode du client par requete, nommee
`compute_route_matrix(origin, destinations, mode)` renvoyant
`dict[poi_id, dict|None]` (le dict par POI portant 'distance_m'/'duration_s' bruts
Google ; None si pas de route). Le helper `_make_client` centralise cette interface :
si le developpeur retient un autre nom/forme (ex. methode `__call__`, ou retour de
la reponse JSON brute Google a parser dans le module), SEUL ce helper est a adapter
cote testeur. Ce choix est signale dans le rapport de phase A.
"""

import re

import pytest


# Coordonnees de test (mode adresse).
TEST_LAT = 49.1150
TEST_LON = 6.1650

POI_WALK = {"cathedrale": (49.1203, 6.1758), "gare": (49.1097, 6.1773),
            "pompidou": (49.1095, 6.1825)}
POI_DRIVE = {"a31": (49.1107, 6.1305)}


# ===========================================================================
# Mock client — interface SUPPOSEE (voir HOOK en tete de fichier)
# ===========================================================================
class _MockRoutesClient:
    """Client Google mocke. `responses` mappe poi_id -> dict|None (resultat brut
    par POI). `raise_exc` (si fourni) est levee a chaque appel (chemin reel du
    fallback, AC9). `calls` enregistre les appels pour les sondes de compteur."""

    def __init__(self, responses=None, raise_exc=None):
        self.responses = responses or {}
        self.raise_exc = raise_exc
        self.calls = []

    def compute_route_matrix(self, origin, destinations, mode):
        self.calls.append({"origin": origin, "destinations": dict(destinations),
                           "mode": mode})
        if self.raise_exc is not None:
            raise self.raise_exc
        out = {}
        for poi_id in destinations:
            out[poi_id] = self.responses.get(poi_id)
        return out


def _make_client(responses=None, raise_exc=None):
    return _MockRoutesClient(responses=responses, raise_exc=raise_exc)


def _route(distance_m, duration_s):
    """Resultat brut Google pour un POI (entiers, valeurs non inventees)."""
    return {"distance_m": int(distance_m), "duration_s": int(duration_s)}


# ===========================================================================
# AC7 — compute_travel_times avec routes valides -> dict par POI types entiers
# ===========================================================================
def test_ac7_valid_routes_return_int_fields():
    """AC7 : un client mocke renvoyant des routes valides produit, par POI,
    {'mode': <mode>, 'distance_m': int, 'duration_s': int} avec les VALEURS du mock
    (non inventees). Rouge tant que compute_travel_times n'existe pas."""
    from app.routing import compute_travel_times

    client = _make_client(responses={
        "cathedrale": _route(620, 480),
        "gare": _route(900, 700),
        "pompidou": _route(1100, 820),
    })
    out = compute_travel_times((TEST_LAT, TEST_LON), POI_WALK, "WALK", client=client)

    assert set(out) == set(POI_WALK), f"AC7 : un resultat par POI attendu, recu {set(out)}"
    cath = out["cathedrale"]
    assert cath is not None, "AC7 : route valide attendue pour cathedrale"
    assert cath["mode"] == "WALK", f"AC7 : mode 'WALK' attendu, recu {cath.get('mode')!r}"
    assert cath["distance_m"] == 620 and isinstance(cath["distance_m"], int), (
        f"AC7 : distance_m=620 (int, valeur du mock), recu {cath.get('distance_m')!r}"
    )
    assert cath["duration_s"] == 480 and isinstance(cath["duration_s"], int), (
        f"AC7 : duration_s=480 (int, valeur du mock), recu {cath.get('duration_s')!r}"
    )


# ===========================================================================
# AC8 — repli cle absente + client None : None partout, sans reseau ni exception
# ===========================================================================
def test_ac8_no_key_no_client_returns_all_none(monkeypatch):
    """AC8 : GOOGLE_MAPS_API_KEY non defini ET client=None -> {poi_id: None} pour
    TOUS les POI, sans lever, sans construire de client (pas d'appel reseau).
    Rouge tant que le repli immediat n'est pas implemente."""
    from app import routing

    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)

    # Sonde "aucun client construit" : si le module a une fabrique de client
    # interne, elle ne doit JAMAIS etre appelee quand la cle est absente.
    if hasattr(routing, "_build_client"):
        def _boom(*a, **k):
            raise AssertionError("AC8 : aucun client ne doit etre construit sans cle")
        monkeypatch.setattr(routing, "_build_client", _boom)

    out = routing.compute_travel_times((TEST_LAT, TEST_LON), POI_WALK, "WALK", client=None)
    assert set(out) == set(POI_WALK)
    assert all(v is None for v in out.values()), (
        f"AC8 : None partout attendu sans cle ni client, recu {out!r}"
    )


# ===========================================================================
# AC9 — repli reseau KO (chemin reel : le client mocke LEVE)
# ===========================================================================
def test_ac9_client_raises_returns_all_none_without_propagating():
    """AC9 : un client mocke dont la methode d'appel LEVE -> {poi_id: None} pour
    tous les POI, sans propager l'exception (lecon 9.10 : faire lever la vraie
    dependance, pas un stub qui renvoie deja le repli)."""
    from app.routing import compute_travel_times

    client = _make_client(raise_exc=RuntimeError("network down"))
    out = compute_travel_times((TEST_LAT, TEST_LON), POI_WALK, "WALK", client=client)
    assert set(out) == set(POI_WALK)
    assert all(v is None for v in out.values()), (
        f"AC9 : None partout quand le client leve, recu {out!r}"
    )
    assert client.calls, "AC9 : le client mocke doit avoir ete reellement appele (chemin reel)"


# ===========================================================================
# AC10 — reponse invalide pour UN POI : repli par element (les autres OK)
# ===========================================================================
def test_ac10_partial_invalid_response_is_per_poi():
    """AC10 : si un POI a une reponse malformee/None (status non-OK), il vaut None
    et les AUTRES restent corrects. Repli par element, pas global."""
    from app.routing import compute_travel_times

    client = _make_client(responses={
        "cathedrale": _route(620, 480),
        "gare": None,                       # pas de route pour ce POI
        "pompidou": _route(1100, 820),
    })
    out = compute_travel_times((TEST_LAT, TEST_LON), POI_WALK, "WALK", client=client)
    assert out["gare"] is None, f"AC10 : gare sans route -> None, recu {out['gare']!r}"
    assert out["cathedrale"] is not None and out["cathedrale"]["duration_s"] == 480, (
        f"AC10 : cathedrale doit rester correcte malgre l'echec d'un autre POI, "
        f"recu {out['cathedrale']!r}"
    )
    assert out["pompidou"] is not None, "AC10 : pompidou doit rester correct"


# ===========================================================================
# AC11 — cache memoire : 1 seul appel client sur 2 requetes identiques, reset
# ===========================================================================
def test_ac11_cache_hit_then_reset_redrives_client():
    """AC11 : deux appels successifs meme origine/poi/mode -> UN SEUL appel client
    (cache hit au 2e). Apres reset_routing_cache(), un nouvel appel re-declenche le
    client. Le reset autouse du conftest garantit l'isolation inter-tests."""
    from app.routing import compute_travel_times, reset_routing_cache

    dest = {"cathedrale": (49.1203, 6.1758)}
    client = _make_client(responses={"cathedrale": _route(620, 480)})

    compute_travel_times((TEST_LAT, TEST_LON), dest, "WALK", client=client)
    compute_travel_times((TEST_LAT, TEST_LON), dest, "WALK", client=client)
    assert len(client.calls) == 1, (
        f"AC11 : un seul appel client attendu (cache hit au 2e), recu {len(client.calls)}"
    )

    reset_routing_cache()
    compute_travel_times((TEST_LAT, TEST_LON), dest, "WALK", client=client)
    assert len(client.calls) == 2, (
        f"AC11 : apres reset, le client doit etre re-declenche (2 appels), recu "
        f"{len(client.calls)}"
    )


# ===========================================================================
# AC12 — pas de persistance : _CACHE est un dict module, aucune table/fichier
# ===========================================================================
def test_ac12_cache_is_in_memory_dict_and_resettable():
    """AC12 : le cache de app.routing est un dict module (memoire), vide par
    reset_routing_cache() ; aucune persistance disque/DB (CGU Google). On verifie
    que _CACHE est bien un dict et qu'apres un appel + reset il redevient vide."""
    from app import routing

    assert isinstance(routing._CACHE, dict), (
        f"AC12 : _CACHE doit etre un dict module en memoire, recu {type(routing._CACHE)!r}"
    )
    client = _make_client(responses={"cathedrale": _route(620, 480)})
    routing.compute_travel_times((TEST_LAT, TEST_LON), {"cathedrale": (49.12, 6.17)},
                                 "WALK", client=client)
    assert routing._CACHE, "AC12 : le cache doit se peupler en memoire apres un appel"
    routing.reset_routing_cache()
    assert routing._CACHE == {}, (
        f"AC12 : reset_routing_cache() doit vider le cache, recu {routing._CACHE!r}"
    )


def test_ac12_no_disk_persistence_module_inspection():
    """AC12 (statique) : le module routing n'ouvre pas de fichier/DB pour les temps
    (pas de SessionLocal, pas d'open() en ecriture, pas de sqlite). Sonde de
    regression legere sur le texte du module."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "app" / "routing.py"
    content = src.read_text(encoding="utf-8")
    for forbidden in ("SessionLocal", "sqlite3", "open("):
        assert forbidden not in content, (
            f"AC12 : routing.py ne doit pas persister ({forbidden!r} interdit, CGU "
            f"Google : cache memoire uniquement)"
        )


# ===========================================================================
# Fixtures communes — geocode + analyze_semantic + routing pour les AC analyse
# ===========================================================================
def _fake_listing(city="Metz", district="Sablon"):
    return {
        "transparency_score": 70, "verdict": "Bonne", "risk_level": "Faible",
        "summary": "RAS.", "risk_summary": "RAS.", "questions": [],
        "negotiation_levers": [], "local_claims": [],
        "listing": {
            "city": city, "district": district, "property_type": "appartement",
            "surface_m2": 70.0, "price_total": 210000.0, "dpe": None,
            "construction_year": None, "floor": None, "has_elevator": None,
            "has_terrace": None, "has_balcony": None, "has_cellar": None,
            "parking": None, "bedrooms": None, "condo_fees": None,
        },
    }


@pytest.fixture()
def patch_geo_and_llm(monkeypatch):
    """Geocode -> coords connues (mode adresse) + analyze_semantic deterministe.
    Patche les symboles tels qu'importes par app.analysis."""
    import app.analysis as analysis_mod

    monkeypatch.setattr(
        analysis_mod, "geocode_address",
        lambda addr, city="Metz": {
            "lat": TEST_LAT, "lon": TEST_LON, "score": 0.9,
            "label": "Adresse Test Metz", "city": "Metz", "citycode": "57463",
            "postcode": "57000",
        },
    )
    monkeypatch.setattr(analysis_mod, "analyze_semantic",
                        lambda raw_text: _fake_listing())


def _patch_routing_returning(monkeypatch, walk_results, drive_results):
    """Patche metz_local.compute_travel_times : renvoie walk_results pour un appel
    WALK, drive_results pour un appel DRIVE. Enregistre les appels (sonde AC14).
    HOOK : on suppose que metz_local importe compute_travel_times de app.routing et
    l'appelle par mode. Si l'aiguillage vit dans analysis au lieu de metz_local, le
    developpeur signalera ou patcher (cote testeur)."""
    import app.metz_local as ml

    calls = []

    def _fake(origin, destinations, mode, client=None):
        calls.append({"mode": mode, "poi_ids": set(destinations)})
        if mode == "WALK":
            return {p: walk_results.get(p) for p in destinations}
        if mode == "DRIVE":
            return {p: drive_results.get(p) for p in destinations}
        return {p: None for p in destinations}

    monkeypatch.setattr(ml, "compute_travel_times", _fake, raising=False)
    return calls


# ===========================================================================
# AC13 — mode par defaut : facts portent un temps + champs routes
# ===========================================================================
def test_ac13_default_mode_produces_routed_facts(monkeypatch):
    """AC13 : routing mocke renvoyant des temps WALK (cathedrale/gare/pompidou) et
    DRIVE (a31) -> les facts correspondants sont des TEMPS ('~N min à pied' /
    '~N min en voiture'), portent mode/duration_s/distance_m/estimated=false/poi_id.
    Rouge tant que local_context_from_coords n'integre pas le routing."""
    walk = {
        "cathedrale": {"mode": "WALK", "distance_m": 620, "duration_s": 480},
        "gare": {"mode": "WALK", "distance_m": 900, "duration_s": 700},
        "pompidou": {"mode": "WALK", "distance_m": 1100, "duration_s": 820},
    }
    drive = {"a31": {"mode": "DRIVE", "distance_m": 5200, "duration_s": 600}}
    _patch_routing_returning(monkeypatch, walk, drive)

    from app.metz_local import local_context_from_coords

    ctx = local_context_from_coords(TEST_LAT, TEST_LON)
    by_id = {f.get("poi_id"): f for f in ctx["facts"] if f.get("poi_id")}
    assert "cathedrale" in by_id, (
        f"AC13 : les facts POI routes doivent porter poi_id, recu "
        f"{[f.get('label') for f in ctx['facts']]}"
    )
    cath = by_id["cathedrale"]
    assert cath.get("estimated") is False, f"AC13 : estimated=false attendu, recu {cath}"
    assert cath.get("mode") == "WALK" and cath.get("duration_s") == 480, (
        f"AC13 : mode/duration_s routes attendus, recu {cath}"
    )
    assert re.search(r"~\d+\s*min à pied", cath["value"]), (
        f"AC13 : value cathedrale doit etre '~N min à pied', recu {cath['value']!r}"
    )
    a31 = by_id.get("a31")
    assert a31 is not None and re.search(r"~\d+\s*min en voiture", a31["value"]), (
        f"AC13 : value a31 doit etre '~N min en voiture', recu "
        f"{a31['value'] if a31 else None!r}"
    )


# ===========================================================================
# AC14 — 2 requetes : WALK {cathedrale,gare,pompidou} + DRIVE {a31}
# ===========================================================================
def test_ac14_default_routing_emits_exactly_two_calls(monkeypatch):
    """AC14 : le routing par defaut emet EXACTEMENT 2 appels compute_travel_times :
    un WALK sur {cathedrale, gare, pompidou}, un DRIVE sur {a31}. Sonde sur les
    arguments (mode ET ensemble des poi_id de chaque appel), pas seulement le
    nombre. Le reset autouse du conftest garantit qu'aucun cache hit ne masque un
    appel."""
    walk = {p: {"mode": "WALK", "distance_m": 600, "duration_s": 480} for p in
            ("cathedrale", "gare", "pompidou")}
    drive = {"a31": {"mode": "DRIVE", "distance_m": 5200, "duration_s": 600}}
    calls = _patch_routing_returning(monkeypatch, walk, drive)

    from app.metz_local import local_context_from_coords
    local_context_from_coords(TEST_LAT, TEST_LON)

    assert len(calls) == 2, (
        f"AC14 : exactement 2 appels compute_travel_times attendus, recu {len(calls)} "
        f": {calls}"
    )
    walk_calls = [c for c in calls if c["mode"] == "WALK"]
    drive_calls = [c for c in calls if c["mode"] == "DRIVE"]
    assert len(walk_calls) == 1 and len(drive_calls) == 1, (
        f"AC14 : 1 WALK + 1 DRIVE attendus, recu {calls}"
    )
    assert walk_calls[0]["poi_ids"] == {"cathedrale", "gare", "pompidou"}, (
        f"AC14 : WALK sur {{cathedrale, gare, pompidou}}, recu {walk_calls[0]['poi_ids']}"
    )
    assert drive_calls[0]["poi_ids"] == {"a31"}, (
        f"AC14 : DRIVE sur {{a31}}, recu {drive_calls[0]['poi_ids']}"
    )


# ===========================================================================
# AC15 — repli par POI : cathedrale routee, gare en Haversine
# ===========================================================================
def test_ac15_per_poi_fallback(monkeypatch):
    """AC15 : routing renvoyant un temps pour cathedrale mais None pour gare ->
    cathedrale = temps (estimated=false), gare = Haversine (estimated=true, value
    finissant par 'à vol d'oiseau'). Repli INDEPENDANT par POI."""
    walk = {
        "cathedrale": {"mode": "WALK", "distance_m": 620, "duration_s": 480},
        "gare": None,
        "pompidou": {"mode": "WALK", "distance_m": 1100, "duration_s": 820},
    }
    drive = {"a31": {"mode": "DRIVE", "distance_m": 5200, "duration_s": 600}}
    _patch_routing_returning(monkeypatch, walk, drive)

    from app.metz_local import local_context_from_coords
    ctx = local_context_from_coords(TEST_LAT, TEST_LON)
    by_id = {f.get("poi_id"): f for f in ctx["facts"] if f.get("poi_id")}

    assert by_id["cathedrale"].get("estimated") is False, (
        f"AC15 : cathedrale routee (estimated=false), recu {by_id['cathedrale']}"
    )
    gare = by_id["gare"]
    assert gare.get("estimated") is True, (
        f"AC15 : gare en repli Haversine (estimated=true), recu {gare}"
    )
    assert gare["value"].rstrip().endswith("à vol d'oiseau"), (
        f"AC15 : value gare doit finir par 'à vol d'oiseau', recu {gare['value']!r}"
    )
    assert not re.search(r"~\d+\s*min", gare["value"]), (
        f"AC15 : un repli Haversine ne doit pas afficher de minutes, recu {gare['value']!r}"
    )


# ===========================================================================
# AC16 — routing indisponible global (None partout) : 4 facts Haversine, 200
# ===========================================================================
def test_ac16_routing_unavailable_all_haversine(monkeypatch):
    """AC16 : compute_travel_times renvoyant None partout (cle absente) -> les 4
    facts POI sont en Haversine etiquete 'à vol d'oiseau'. Comportement identique a
    l'actuel sans routing."""
    _patch_routing_returning(monkeypatch, {}, {})  # tout None

    from app.metz_local import local_context_from_coords
    ctx = local_context_from_coords(TEST_LAT, TEST_LON)
    poi_facts = [f for f in ctx["facts"]
                 if f["label"] in (
                     "Centre / Cathédrale St-Étienne", "Gare Metz-Ville",
                     "Centre Pompidou-Metz", "Échangeur A31 le plus proche")]
    assert len(poi_facts) == 4, f"AC16 : 4 facts POI attendus, recu {len(poi_facts)}"
    for f in poi_facts:
        assert f.get("estimated") in (True, None), (
            f"AC16 : facts en repli Haversine attendus, recu {f}"
        )
        assert "à vol d'oiseau" in f["value"], (
            f"AC16 : value en Haversine attendue ('à vol d'oiseau'), recu {f['value']!r}"
        )


def test_ac16_analyze_returns_200_when_routing_unavailable(client, monkeypatch):
    """AC16 (HTTP) : avec routing indisponible (None partout), /analyze renvoie 200
    (pas de 500). Geocode + LLM patches ; routing patche au niveau metz_local."""
    import app.analysis as analysis_mod
    import app.metz_local as ml

    monkeypatch.setattr(
        analysis_mod, "geocode_address",
        lambda addr, city="Metz": {
            "lat": TEST_LAT, "lon": TEST_LON, "score": 0.9,
            "label": "Adresse Test", "city": "Metz", "citycode": "57463",
            "postcode": "57000",
        },
    )
    monkeypatch.setattr(analysis_mod, "analyze_semantic", lambda raw_text: _fake_listing())
    monkeypatch.setattr(
        ml, "compute_travel_times",
        lambda origin, destinations, mode, client=None: {p: None for p in destinations},
        raising=False,
    )

    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement Sablon Metz 70 m2.", "address": "3 Rue Test Metz"},
        headers={"Fly-Client-IP": "203.0.113.20"},
    )
    assert resp.status_code == 200, (
        f"AC16 : /analyze doit renvoyer 200 meme sans routing, recu {resp.status_code}"
    )


# ===========================================================================
# AC17 — /analyze robuste au routing qui LEVE (chemin reel)
# ===========================================================================
def test_ac17_analyze_robust_when_routing_raises(client, monkeypatch):
    """AC17 : en faisant LEVER compute_travel_times (monkeypatch qui raise),
    run_full_analysis en mode adresse retourne un contexte local valide en
    Haversine et /analyze renvoie 200. Lecon 9.10 : on fait lever la vraie
    dependance, pas la facade."""
    import app.analysis as analysis_mod
    import app.metz_local as ml

    monkeypatch.setattr(
        analysis_mod, "geocode_address",
        lambda addr, city="Metz": {
            "lat": TEST_LAT, "lon": TEST_LON, "score": 0.9, "label": "Adr",
            "city": "Metz", "citycode": "57463", "postcode": "57000",
        },
    )
    monkeypatch.setattr(analysis_mod, "analyze_semantic", lambda raw_text: _fake_listing())

    def _boom(origin, destinations, mode, client=None):
        raise RuntimeError("routing exploded")

    monkeypatch.setattr(ml, "compute_travel_times", _boom, raising=False)

    from app.analysis import run_full_analysis
    out = run_full_analysis("Appartement Sablon Metz 70 m2.", address="3 Rue Test Metz")
    lc = out.get("local_context") or {}
    assert lc, "AC17 : un local_context valide attendu malgre l'exception routing"
    poi_facts = [f for f in lc.get("facts", []) if f.get("poi_id") or "Échangeur" in f["label"]]
    assert poi_facts, "AC17 : des facts POI attendus en repli"
    for f in poi_facts:
        assert "à vol d'oiseau" in f["value"], (
            f"AC17 : repli Haversine attendu quand routing leve, recu {f['value']!r}"
        )

    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement Sablon Metz.", "address": "3 Rue Test Metz"},
        headers={"Fly-Client-IP": "203.0.113.21"},
    )
    assert resp.status_code == 200, (
        f"AC17 : /analyze doit renvoyer 200 quand le routing leve, recu {resp.status_code}"
    )


# ===========================================================================
# AC23 — etiquetage honnete : un repli (estimated=true) n'affiche jamais de minutes
# ===========================================================================
def test_ac23_estimated_facts_have_no_minutes(monkeypatch):
    """AC23 : un fact en repli Haversine porte estimated=true, son value finit par
    'à vol d'oiseau' et n'affiche jamais '~N min'. On force le repli global (None
    partout) -> les 4 POI sont des replis. On asserte qu'AU MOINS un fact estimated
    existe (sinon assertion vacue), puis l'invariant sur CHACUN. Rouge tant que le
    repli n'est pas etiquete (code actuel : pas de champ estimated, pas de suffixe)."""
    _patch_routing_returning(monkeypatch, {}, {})

    from app.metz_local import local_context_from_coords
    ctx = local_context_from_coords(TEST_LAT, TEST_LON)
    poi_facts = [f for f in ctx["facts"] if f.get("poi_id") or "Échangeur" in f["label"]]
    estimated_facts = [f for f in poi_facts if f.get("estimated") is True]
    assert estimated_facts, (
        "AC23 : en repli global, les facts POI doivent porter estimated=true "
        f"(sinon l'invariant est vacue). Facts={poi_facts}"
    )
    for f in estimated_facts:
        assert not re.search(r"~\d+\s*min", f["value"]), (
            f"AC23 : un fact estimated ne doit pas afficher de minutes, recu "
            f"{f['value']!r}"
        )
        assert f["value"].rstrip().endswith("à vol d'oiseau"), (
            f"AC23 : un fact estimated doit finir par 'à vol d'oiseau', recu "
            f"{f['value']!r}"
        )


# ===========================================================================
# AC24 — un temps reel (estimated=false) n'affiche jamais 'à vol d'oiseau'
# ===========================================================================
def test_ac24_routed_facts_never_vol_oiseau(monkeypatch):
    """AC24 : aucun fact a temps reel (estimated=false) n'affiche 'à vol d'oiseau' ;
    son label_mode (s'il existe) ∈ {à pied, en voiture, à vélo, en transports} et
    jamais 'à vol d'oiseau'."""
    walk = {p: {"mode": "WALK", "distance_m": 600, "duration_s": 480}
            for p in ("cathedrale", "gare", "pompidou")}
    drive = {"a31": {"mode": "DRIVE", "distance_m": 5200, "duration_s": 600}}
    _patch_routing_returning(monkeypatch, walk, drive)

    from app.metz_local import local_context_from_coords
    ctx = local_context_from_coords(TEST_LAT, TEST_LON)
    allowed_modes = {"à pied", "en voiture", "à vélo", "en transports"}
    routed_facts = [f for f in ctx["facts"] if f.get("estimated") is False]
    assert routed_facts, (
        "AC24 : avec un routing mocke renvoyant des temps, des facts estimated=false "
        f"sont attendus (sinon l'invariant est vacue). Facts={ctx['facts']}"
    )
    for f in routed_facts:
        assert "à vol d'oiseau" not in f["value"], (
            f"AC24 : un temps reel ne doit pas afficher 'à vol d'oiseau', recu "
            f"{f['value']!r}"
        )
        lm = f.get("label_mode")
        if lm is not None:
            assert lm in allowed_modes, (
                f"AC24 : label_mode invalide {lm!r}, attendu dans {allowed_modes}"
            )


# ===========================================================================
# AC25 — value d'un temps reel derive de duration_s, pas d'une distance Haversine
# ===========================================================================
def test_ac25_value_derived_from_duration_not_distance(monkeypatch):
    """AC25 : le value d'un temps reel = round(duration_s/60) min, INDEPENDANT de la
    distance Haversine. Sonde : on fixe duration_s=480 (8 min) et un distance_m
    deliberement incoherent avec la distance Haversine reelle ; le value doit valoir
    '~8 min', preuve qu'il derive bien de duration_s."""
    walk = {
        "cathedrale": {"mode": "WALK", "distance_m": 99999, "duration_s": 480},
        "gare": {"mode": "WALK", "distance_m": 1, "duration_s": 700},
        "pompidou": {"mode": "WALK", "distance_m": 1, "duration_s": 820},
    }
    drive = {"a31": {"mode": "DRIVE", "distance_m": 1, "duration_s": 600}}
    _patch_routing_returning(monkeypatch, walk, drive)

    from app.metz_local import local_context_from_coords
    ctx = local_context_from_coords(TEST_LAT, TEST_LON)
    cath = next(f for f in ctx["facts"] if f.get("poi_id") == "cathedrale")
    assert re.search(r"~8\s*min", cath["value"]), (
        f"AC25 : value attendu '~8 min' (round(480/60)), recu {cath['value']!r} "
        f"(le value ne doit pas deriver de distance_m)"
    )


# ===========================================================================
# AC26 — RGPD : aucune lat/lon dans la reponse /analyze (couche qui PRODUIT)
# ===========================================================================
def _has_coord_key(obj):
    """Cherche RECURSIVEMENT une cle lat/lon/latitude/longitude dans un dict/list."""
    coord_keys = {"lat", "lon", "latitude", "longitude"}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in coord_keys:
                return k
            found = _has_coord_key(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _has_coord_key(v)
            if found:
                return found
    return None


def test_ac26_run_full_analysis_dict_has_no_coords(monkeypatch):
    """AC26 (couche qui PRODUIT, lecon 9.10) : le dict renvoye par run_full_analysis
    DIRECTEMENT (hors response_model qui filtre) ne contient aucune cle
    lat/lon/latitude/longitude, ni dans local_context ni dans aucun fact. Routing
    mocke avec des coords reelles en entree."""
    import app.analysis as analysis_mod
    import app.metz_local as ml

    monkeypatch.setattr(
        analysis_mod, "geocode_address",
        lambda addr, city="Metz": {
            "lat": TEST_LAT, "lon": TEST_LON, "score": 0.9, "label": "Adr",
            "city": "Metz", "citycode": "57463", "postcode": "57000",
        },
    )
    monkeypatch.setattr(analysis_mod, "analyze_semantic", lambda raw_text: _fake_listing())
    walk = {p: {"mode": "WALK", "distance_m": 600, "duration_s": 480}
            for p in ("cathedrale", "gare", "pompidou")}
    drive = {"a31": {"mode": "DRIVE", "distance_m": 5200, "duration_s": 600}}
    monkeypatch.setattr(
        ml, "compute_travel_times",
        lambda origin, destinations, mode, client=None: (
            {p: walk.get(p) for p in destinations} if mode == "WALK"
            else {p: drive.get(p) for p in destinations}),
        raising=False,
    )

    from app.analysis import run_full_analysis
    out = run_full_analysis("Appartement Sablon Metz.", address="3 Rue Test Metz")
    found = _has_coord_key(out)
    assert found is None, (
        f"AC26 : aucune cle coordonnee ne doit fuiter dans le dict run_full_analysis,"
        f" trouvee {found!r}"
    )


def test_ac26_analyze_http_body_has_no_coords(client, monkeypatch):
    """AC26 (HTTP) : le corps /analyze ne contient pas non plus de lat/lon
    (verification du serialiseur en complement de la couche productrice)."""
    import app.analysis as analysis_mod
    import app.metz_local as ml

    monkeypatch.setattr(
        analysis_mod, "geocode_address",
        lambda addr, city="Metz": {
            "lat": TEST_LAT, "lon": TEST_LON, "score": 0.9, "label": "Adr",
            "city": "Metz", "citycode": "57463", "postcode": "57000",
        },
    )
    monkeypatch.setattr(analysis_mod, "analyze_semantic", lambda raw_text: _fake_listing())
    monkeypatch.setattr(
        ml, "compute_travel_times",
        lambda origin, destinations, mode, client=None: {p: None for p in destinations},
        raising=False,
    )
    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement Sablon Metz.", "address": "3 Rue Test Metz"},
        headers={"Fly-Client-IP": "203.0.113.22"},
    )
    assert resp.status_code == 200
    found = _has_coord_key(resp.json())
    assert found is None, f"AC26 : aucune coordonnee dans le corps /analyze, trouvee {found!r}"


# ===========================================================================
# AC29 — retro-compat : nouveaux champs de fact tous optionnels (mode quartier)
# ===========================================================================
def test_ac29_quartier_facts_only_label_value(client, monkeypatch):
    """AC29 : une reponse /analyze en mode QUARTIER (sans adresse) a des facts qui
    n'ont que label/value (aucun des nouveaux champs mode/duration_s/distance_m/
    estimated/poi_id) -> LocalContext valide, retro-compatible."""
    import app.analysis as analysis_mod
    monkeypatch.setattr(analysis_mod, "analyze_semantic",
                        lambda raw_text: _fake_listing())

    resp = client.post(
        "/analyze",
        json={"raw_text": "Appartement Sablon Metz, sans adresse."},
        headers={"Fly-Client-IP": "203.0.113.23"},
    )
    assert resp.status_code == 200
    lc = resp.json().get("local_context") or {}
    assert lc.get("precision") == "quartier", (
        f"AC29 : precision 'quartier' attendue sans adresse, recu {lc.get('precision')!r}"
    )
    optional_fields = {"mode", "duration_s", "distance_m", "estimated", "poi_id"}
    for f in lc.get("facts", []):
        extra = set(f) & optional_fields
        assert not extra, (
            f"AC29 : un fact mode quartier ne doit porter aucun champ route, recu "
            f"{extra} dans {f}"
        )


# ===========================================================================
# AC41 — section non-scoree : score inchange avec/sans routing
# ===========================================================================
def test_ac41_score_unchanged_with_or_without_routing(monkeypatch):
    """AC41 : global_score et breakdown 40/30/30 sont identiques que le routing soit
    present (temps mockes) ou absent (None partout). On compare deux analyses
    identiques. Falsifiable : rouge si le routing/ecoles touchait le score."""
    import app.analysis as analysis_mod
    import app.metz_local as ml

    monkeypatch.setattr(
        analysis_mod, "geocode_address",
        lambda addr, city="Metz": {
            "lat": TEST_LAT, "lon": TEST_LON, "score": 0.9, "label": "Adr",
            "city": "Metz", "citycode": "57463", "postcode": "57000",
        },
    )
    monkeypatch.setattr(analysis_mod, "analyze_semantic", lambda raw_text: _fake_listing())

    from app.analysis import run_full_analysis

    # Sans routing (None partout).
    monkeypatch.setattr(
        ml, "compute_travel_times",
        lambda origin, destinations, mode, client=None: {p: None for p in destinations},
        raising=False,
    )
    out_without = run_full_analysis("Appartement Sablon Metz.", address="3 Rue Test Metz")

    # Avec routing (temps mockes).
    walk = {p: {"mode": "WALK", "distance_m": 600, "duration_s": 480}
            for p in ("cathedrale", "gare", "pompidou")}
    drive = {"a31": {"mode": "DRIVE", "distance_m": 5200, "duration_s": 600}}
    ml_reset = getattr(__import__("app.routing", fromlist=["reset_routing_cache"]),
                       "reset_routing_cache", None)
    if ml_reset:
        ml_reset()
    monkeypatch.setattr(
        ml, "compute_travel_times",
        lambda origin, destinations, mode, client=None: (
            {p: walk.get(p) for p in destinations} if mode == "WALK"
            else {p: drive.get(p) for p in destinations}),
        raising=False,
    )
    out_with = run_full_analysis("Appartement Sablon Metz.", address="3 Rue Test Metz")

    assert out_without["global_score"] == out_with["global_score"], (
        f"AC41 : global_score doit etre inchange (sans={out_without['global_score']}, "
        f"avec={out_with['global_score']})"
    )
    pts_without = [(p["label"], p.get("points")) for p in out_without["pillars"]]
    pts_with = [(p["label"], p.get("points")) for p in out_with["pillars"]]
    assert pts_without == pts_with, (
        f"AC41 : breakdown 40/30/30 inchange attendu, sans={pts_without} avec={pts_with}"
    )


# ===========================================================================
# AC42 — anti-patterns produit : pas d'estimation de prix / DVF / redistribution
# ===========================================================================
def test_ac42_no_price_estimation_in_facts(monkeypatch):
    """AC42 : aucun fact/claim ajoute ne contient d'estimation de prix, de reference
    DVF, ni de redistribution d'annonce. Sonde de regression legere sur les facts du
    contexte local (mode adresse, routing + ecoles mockes)."""
    import app.analysis as analysis_mod
    import app.metz_local as ml

    monkeypatch.setattr(
        analysis_mod, "geocode_address",
        lambda addr, city="Metz": {
            "lat": TEST_LAT, "lon": TEST_LON, "score": 0.9, "label": "Adr",
            "city": "Metz", "citycode": "57463", "postcode": "57000",
        },
    )
    monkeypatch.setattr(analysis_mod, "analyze_semantic", lambda raw_text: _fake_listing())
    walk = {p: {"mode": "WALK", "distance_m": 600, "duration_s": 480}
            for p in ("cathedrale", "gare", "pompidou")}
    drive = {"a31": {"mode": "DRIVE", "distance_m": 5200, "duration_s": 600}}
    monkeypatch.setattr(
        ml, "compute_travel_times",
        lambda origin, destinations, mode, client=None: (
            {p: walk.get(p) for p in destinations} if mode == "WALK"
            else {p: drive.get(p) for p in destinations}),
        raising=False,
    )

    from app.analysis import run_full_analysis
    out = run_full_analysis("Appartement Sablon Metz.", address="3 Rue Test Metz")
    lc = out.get("local_context") or {}
    forbidden = ("€/m² estimé", "valeur estimée", "dvf", "prix estimé", "estimation de prix")
    blobs = []
    for f in lc.get("facts", []):
        blobs.append((f.get("label", "") + " " + f.get("value", "")).lower())
    for c in lc.get("claims", []):
        blobs.append((c.get("text", "") + " " + c.get("note", "")).lower())
    for blob in blobs:
        for word in forbidden:
            assert word.lower() not in blob, (
                f"AC42 : anti-pattern {word!r} interdit dans le contexte local, recu "
                f"dans {blob!r}"
            )
