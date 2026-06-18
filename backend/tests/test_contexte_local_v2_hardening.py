"""Tests de DURCISSEMENT (phase B, challenge adversarial) — Contexte local v2.

Ajoutés par le testeur après livraison du code (suite verte 670). Chaque test
verrouille un invariant à risque de faux-vert OU comble un trou de couverture
identifié au challenge ; chaque durcissement est prouvé falsifiable (rouge si le
code régresse) dans le rapport de phase B.

Périmètre :
- H1 : garde-fou anti-fausse-précision sur la constante `_A31_LUXEMBOURG`
  (leçon remontée par le développeur : la mention A31 ne doit JAMAIS embarquer un
  temps chiffré « ~N min », sinon le fact a31 en repli Haversine afficherait des
  minutes alors qu'il est `estimated=true` — viole AC23/AC25). Le code actuel place
  la mention A31 en PRÉFIXE du value et y a retiré « (~45 min hors trafic) ».
- H2 : plausibilité géographique des coordonnées du snapshot écoles RÉEL
  (complète AC34 qui ne contrôle que la commune + le degré, pas les coords). Une
  coord à 0,0, hors bbox Metz élargie, ou avec lat/lon inversés = donnée fausse
  (exigence produit : donnée factuelle). Falsifiable en injectant une coord aberrante.
- H3 : aucun jugement de valeur dans le snapshot écoles RÉEL (noms/communes).
- H4 : endpoint /travel-times — un mode réel TRANSIT/BICYCLE produit un label_mode
  correct et JAMAIS « à vol d'oiseau » sur un temps réel (étiquetage honnête,
  AC24 étendu aux modes à-la-demande, pas seulement WALK/DRIVE du défaut).
- H5 : le repli /travel-times (estimated=true) n'affiche jamais « ~N min »
  (AC23 côté endpoint, non couvert par les tests existants qui ne forcent pas le
  repli sur l'endpoint).

AUCUN appel réseau / LLM : client routing mocké, geocode patché. Isolation par les
fixtures autouse du conftest (_reset_routing_cache).
"""

import re
from pathlib import Path

import pytest

import app.main as main


REF_LAT = 49.1193
REF_LON = 6.1757


# ===========================================================================
# H1 — _A31_LUXEMBOURG ne contient AUCUN temps chiffré (anti fausse précision)
# ===========================================================================
def test_h1_a31_luxembourg_constant_has_no_minutes():
    """H1 : la constante `_A31_LUXEMBOURG` (mention frontalière préfixée au value du
    fact a31) ne doit contenir AUCUN temps chiffré (`~N min`, `N min`, `N minutes`).
    Garde-fou de la leçon remontée par le dev : un temps chiffré dans cette mention
    referait afficher des minutes sur le fact a31 en repli Haversine (estimated=true),
    violant AC23/AC25. Falsifiable : rouge si l'on réintroduit « (~45 min hors
    trafic) »."""
    from app.metz_local import _A31_LUXEMBOURG

    assert not re.search(r"~?\d+\s*min", _A31_LUXEMBOURG), (
        f"H1 : aucun temps chiffré ne doit figurer dans _A31_LUXEMBOURG "
        f"(anti fausse précision), recu {_A31_LUXEMBOURG!r}"
    )
    assert not re.search(r"\d+\s*minutes?", _A31_LUXEMBOURG, re.IGNORECASE), (
        f"H1 : aucune mention 'N minutes' dans _A31_LUXEMBOURG, recu {_A31_LUXEMBOURG!r}"
    )


def test_h1_a31_real_fallback_fact_no_minutes_keeps_luxembourg(monkeypatch):
    """H1 (bout-en-bout, repli RÉEL) : en repli Haversine (compute_travel_times -> None
    partout, comme sans clé), le fact a31 contient « Luxembourg » (AC3), finit par
    « à vol d'oiseau » (AC23) et n'affiche AUCUN temps en minutes — y compris dans son
    préfixe A31. Verrouille la réconciliation AC3↔AC23 sur le fact a31 réel."""
    import app.metz_local as ml

    monkeypatch.setattr(
        ml, "compute_travel_times",
        lambda origin, destinations, mode, client=None: {p: None for p in destinations},
        raising=False,
    )
    ctx = ml.local_context_from_coords(REF_LAT, REF_LON)
    a31 = next(f for f in ctx["facts"] if "A31" in f["label"])
    assert a31.get("estimated") is True, f"H1 : a31 doit être en repli, recu {a31}"
    assert "Luxembourg" in a31["value"], f"H1 : AC3 — Luxembourg attendu, recu {a31['value']!r}"
    assert a31["value"].rstrip().endswith("à vol d'oiseau"), (
        f"H1 : AC23 — value a31 doit finir par 'à vol d'oiseau', recu {a31['value']!r}"
    )
    assert not re.search(r"~?\d+\s*min", a31["value"]), (
        f"H1 : aucun temps en minutes sur le fact a31 estimated, recu {a31['value']!r}"
    )


# ===========================================================================
# H2 — plausibilité géographique des coords du snapshot écoles RÉEL
# ===========================================================================
def test_h2_real_snapshot_coords_in_metz_bbox():
    """H2 : toutes les écoles du snapshot RÉEL ont des coords dans une bbox Metz
    élargie (lat 48.95-49.25, lon 6.00-6.30) — pas de 0,0, pas d'inversion lat/lon
    (un lon ~6 placé en lat échouerait), pas de coord aberrante. Complète AC34 (qui
    ne contrôle que commune + degré). Falsifiable : rouge si une école porte une
    coord hors zone ou inversée."""
    from app.schools import _load_schools

    snapshot = _load_schools()
    assert snapshot, "H2 : snapshot réel non vide attendu"
    LAT_MIN, LAT_MAX = 48.95, 49.25
    LON_MIN, LON_MAX = 6.00, 6.30
    for s in snapshot:
        lat, lon = s["lat"], s["lon"]
        assert not (lat == 0 and lon == 0), f"H2 : coord 0,0 interdite pour {s['name']!r}"
        assert LAT_MIN <= lat <= LAT_MAX, (
            f"H2 : lat {lat} hors bbox Metz pour {s['name']!r} (inversion lat/lon ?)"
        )
        assert LON_MIN <= lon <= LON_MAX, (
            f"H2 : lon {lon} hors bbox Metz pour {s['name']!r} (inversion lat/lon ?)"
        )


def test_h2_real_snapshot_covers_multiple_degres_and_communes():
    """H2 (richesse) : le snapshot réel couvre les 4 degrés et plusieurs communes
    (pas un fichier dégénéré à une seule entrée). Donnée factuelle exploitable."""
    from app.schools import _load_schools

    snapshot = _load_schools()
    degres = {s["degre"] for s in snapshot}
    communes = {s["commune"] for s in snapshot}
    assert degres == {"maternelle", "elementaire", "college", "lycee"}, (
        f"H2 : les 4 degrés doivent être présents, recu {degres}"
    )
    assert len(communes) >= 3, (
        f"H2 : plusieurs communes attendues (Metz + couronne), recu {communes}"
    )


# ===========================================================================
# H3 — aucun jugement de valeur dans le snapshot écoles RÉEL
# ===========================================================================
def test_h3_real_snapshot_no_value_judgement():
    """H3 : aucun nom/commune du snapshot réel ne contient de jugement de valeur
    (« prisé », « recherché », « bien desservi », « réputé »…). Donnée factuelle pure
    (décision D / AC36 étendu à la donnée source)."""
    from app.schools import _load_schools

    forbidden = ("prisé", "prise", "recherché", "recherche", "bien desservi",
                 "desservi", "réputé", "repute", "excellent", "meilleur")
    for s in _load_schools():
        blob = (str(s.get("name", "")) + " " + str(s.get("commune", ""))).lower()
        for word in forbidden:
            assert word not in blob, (
                f"H3 : mot de jugement {word!r} interdit dans le snapshot, recu {s!r}"
            )


# ===========================================================================
# H4 / H5 — endpoint /travel-times : étiquetage honnête sur TRANSIT/BICYCLE
# ===========================================================================
def _fake_geo(addr, city_hint="Metz"):
    return {"lat": REF_LAT, "lon": REF_LON, "score": 0.9, "label": "X",
            "city": "Metz", "citycode": "57463", "postcode": "57000"}


@pytest.mark.parametrize("mode,expected_label", [
    ("TRANSIT", "en transports"),
    ("BICYCLE", "à vélo"),
])
def test_h4_endpoint_transit_bicycle_label_mode_honest(client, monkeypatch, mode,
                                                       expected_label):
    """H4 : un mode réel TRANSIT/BICYCLE via /travel-times produit un label_mode
    correct et JAMAIS « à vol d'oiseau » sur un temps réel (AC24 étendu aux modes
    à-la-demande, non couverts par les tests AC13/AC24 qui ne testent que WALK/DRIVE).
    Falsifiable : rouge si _MODE_LABELS perdait l'entrée TRANSIT/BICYCLE ou si un
    temps réel portait 'vol d'oiseau'."""
    monkeypatch.setattr(main, "geocode_address", _fake_geo, raising=False)
    monkeypatch.setattr(
        main, "compute_travel_times",
        lambda origin, destinations, m, client=None: {
            p: {"mode": m, "distance_m": 600, "duration_s": 900} for p in destinations
        },
        raising=False,
    )
    resp = client.post(
        "/travel-times", json={"address": "x", "mode": mode},
        headers={"Fly-Client-IP": "198.51.100.40"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("status") == "ok"
    results = body.get("results") or []
    assert results, "H4 : results non vide attendu"
    for r in results:
        assert r.get("estimated") is False, f"H4 : temps réel attendu, recu {r}"
        assert r.get("label_mode") == expected_label, (
            f"H4 : label_mode {expected_label!r} attendu, recu {r.get('label_mode')!r}"
        )
        assert "à vol d'oiseau" not in r["value"], (
            f"H4 : un temps réel ne doit pas afficher 'à vol d'oiseau', recu {r['value']!r}"
        )
        assert re.search(rf"~\d+\s*min {re.escape(expected_label)}", r["value"]), (
            f"H4 : value '~N min {expected_label}' attendu, recu {r['value']!r}"
        )


def test_h5_endpoint_fallback_no_minutes(client, monkeypatch):
    """H5 : en repli sur l'endpoint /travel-times (compute_travel_times -> None
    partout), chaque résultat porte estimated=true, mode='vol_oiseau', value finissant
    par « à vol d'oiseau » et SANS « ~N min » (AC23 côté endpoint, non couvert par les
    tests existants qui ne forcent pas le repli sur /travel-times). Falsifiable :
    rouge si le repli endpoint affichait un temps."""
    monkeypatch.setattr(main, "geocode_address", _fake_geo, raising=False)
    monkeypatch.setattr(
        main, "compute_travel_times",
        lambda origin, destinations, m, client=None: {p: None for p in destinations},
        raising=False,
    )
    resp = client.post(
        "/travel-times", json={"address": "x", "mode": "WALK"},
        headers={"Fly-Client-IP": "198.51.100.41"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("status") == "ok"
    results = body.get("results") or []
    assert results, "H5 : results non vide attendu"
    for r in results:
        assert r.get("estimated") is True, f"H5 : repli estimated=true attendu, recu {r}"
        assert r["value"].rstrip().endswith("à vol d'oiseau"), (
            f"H5 : value repli doit finir par 'à vol d'oiseau', recu {r['value']!r}"
        )
        assert not re.search(r"~\d+\s*min", r["value"]), (
            f"H5 : un repli ne doit pas afficher de minutes, recu {r['value']!r}"
        )


# ===========================================================================
# H6 — sonde statique : routing.py n'importe pas metz_local/analysis (anti-cycle)
# et metz_local importe schools/routing sans cycle top-level (couvert AC31 mais
# on verrouille en plus que routing.py reste autonome).
# ===========================================================================
def test_h6_routing_module_has_no_app_cycle_imports():
    """H6 : routing.py ne doit pas importer metz_local/analysis au top-level
    (autonomie du module, garde-fou cycle leçon issue-100-B). Sonde statique."""
    src = Path(__file__).resolve().parents[1] / "app" / "routing.py"
    content = src.read_text(encoding="utf-8")
    for forbidden in ("import app.metz_local", "from app.metz_local",
                      "import app.analysis", "from app.analysis"):
        assert forbidden not in content, (
            f"H6 : routing.py ne doit pas importer {forbidden!r} (cycle/autonomie)"
        )
