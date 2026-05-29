"""
Diagnostic du scraper Bien'ici — discovery de l'ID de zone interne pour Metz.

Constats précédents :
  - {"city": "metz"} : silencieusement ignoré (renvoie ~938k annonces).
  - {"zoneIdsByTypes": {"zoneIds": ["57463"]}} : total=0
      → le filtre est respecté MAIS l'INSEE brut n'est pas l'ID attendu.
  - {"postalCodes": [...]} : silencieusement ignoré.

Bien'ici utilise des identifiants de zone internes. Ce script :
  1. interroge plusieurs endpoints de suggestion pour découvrir l'ID Metz
  2. teste le filtre avec chaque ID trouvé
  3. en fallback : utilise mapBounds (rectangle GPS autour de Metz)

Aucune écriture en base.
"""

import json
from collections import Counter
from typing import Optional

from scrapers.base import _session, fetch_json, REQUEST_TIMEOUT

ADS_URL = "https://www.bienici.com/realEstateAds.json"
PROPERTY_TYPES = ["house", "flat"]

# Endpoints de suggestion candidats — on essaie tout, on garde ce qui répond.
SUGGEST_ENDPOINTS = [
    "https://www.bienici.com/realEstateAds-suggestions.json",
    "https://res.bienici.com/suggest.json",
    "https://www.bienici.com/suggest.json",
    "https://www.bienici.com/places.json",
]
SUGGEST_QUERIES = [
    {"q": "Metz"},
    {"q": "metz"},
    {"q": "Metz 57000"},
]

# Coordonnées GPS approximatives de Metz (élargies au Grand Metz).
METZ_BBOX = {
    "northEast": {"lat": 49.18, "lng": 6.30},
    "southWest": {"lat": 49.05, "lng": 6.05},
}


def _wrap(inner: dict) -> dict:
    return {"filters": json.dumps(inner)}


# -------------------------- STEP A : suggestion --------------------------

def probe_suggest_endpoint(url: str, params: dict) -> Optional[dict]:
    """GET direct sans wrapping JSON — on attend de la donnée brute."""
    try:
        r = _session.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        print(f"    erreur réseau: {e}")
        return None
    print(f"    HTTP {r.status_code}  bytes={len(r.text)}  "
          f"ct={r.headers.get('content-type','?')[:30]}")
    if r.status_code != 200 or not r.text:
        return None
    try:
        return r.json()
    except ValueError:
        snippet = r.text[:200].replace("\n", " ")
        print(f"    non-JSON : {snippet!r}")
        return None


def step_a_discover_zone_id() -> list:
    """Renvoie la liste des candidats ID trouvés."""
    print("=" * 70)
    print("ÉTAPE A — Découverte de l'ID de zone Metz via endpoints suggest")
    print("=" * 70)

    candidates: list = []
    for endpoint in SUGGEST_ENDPOINTS:
        for q in SUGGEST_QUERIES:
            print(f"\n  GET {endpoint}  params={q}")
            data = probe_suggest_endpoint(endpoint, q)
            if data is None:
                continue
            # On affiche un échantillon pour comprendre la structure
            sample = json.dumps(data, ensure_ascii=False)[:600]
            print(f"    payload start: {sample}")
            # On extrait toutes les valeurs ressemblant à un ID (id, zoneId,
            # placeId...) de tout le JSON, récursivement.
            ids = _extract_ids(data, want="metz")
            if ids:
                print(f"    >> candidats ID Metz : {ids}")
                candidates.extend(ids)
    # déduplique en gardant l'ordre
    seen = set()
    uniq = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    print(f"\n  TOTAL candidats uniques : {uniq}")
    return uniq


def _extract_ids(node, want: str, path: str = "") -> list:
    """Walk récursif. Si un noeud porte un nom contenant 'metz', remonte
    les champs id/zoneId/placeId/_id du même noeud."""
    found = []
    if isinstance(node, dict):
        name_fields = [str(node.get(k, "")).lower()
                       for k in ("name", "title", "label", "libelle", "city")]
        looks_metz = any(want in n for n in name_fields if n)
        if looks_metz:
            for k in ("id", "_id", "zoneId", "placeId", "code", "value"):
                if k in node:
                    found.append(str(node[k]))
        for k, v in node.items():
            found.extend(_extract_ids(v, want, f"{path}.{k}"))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found.extend(_extract_ids(v, want, f"{path}[{i}]"))
    return found


# ----------------- STEP B : test filtre avec chaque ID -------------------

def step_b_test_zone_ids(zone_ids: list) -> None:
    print("\n" + "=" * 70)
    print(f"ÉTAPE B — Test des {len(zone_ids)} candidats ID en filtre")
    print("=" * 70)
    if not zone_ids:
        print("  (aucun candidat à tester)")
        return

    # Pour chaque ID, on essaie 2 formats : brut et avec préfixe '-'
    for raw_id in zone_ids:
        for prefix in ("", "-"):
            test_id = f"{prefix}{raw_id}"
            _test_filter(
                label=f"zoneIds=[{test_id!r}]",
                inner={
                    "size": 20, "from": 0,
                    "filterType": "buy",
                    "propertyType": PROPERTY_TYPES,
                    "zoneIdsByTypes": {"zoneIds": [test_id]},
                },
            )


# ----------------- STEP C : fallback mapBounds GPS -----------------------

def step_c_bbox() -> None:
    print("\n" + "=" * 70)
    print("ÉTAPE C — Fallback : filtre par mapBounds (GPS) autour de Metz")
    print("=" * 70)
    _test_filter(
        label="mapBounds Metz",
        inner={
            "size": 20, "from": 0,
            "filterType": "buy",
            "propertyType": PROPERTY_TYPES,
            "onTheMarket": [True],
            "mapBounds": METZ_BBOX,
        },
    )


# ---------------------------- Helper commun ------------------------------

def _test_filter(label: str, inner: dict) -> None:
    print(f"\n  > {label}")
    print(f"    filtre: {json.dumps(inner, ensure_ascii=False)[:200]}")
    data = fetch_json(ADS_URL, params=_wrap(inner))
    if not isinstance(data, dict):
        print(f"    -> réponse inexploitable ({type(data).__name__})")
        return
    total = data.get("total")
    ads = data.get("realEstateAds", [])
    print(f"    total={total}  annonces page={len(ads)}")
    if not ads:
        return
    cps = Counter(str(a.get("postalCode", ""))[:2] for a in ads)
    print(f"    départements : {dict(cps)}")
    print(f"    3 premières :")
    for a in ads[:3]:
        print(f"      {str(a.get('city',''))[:20]:20} {a.get('postalCode'):>6} "
              f"{str(a.get('propertyType'))[:8]:8} "
              f"{a.get('price'):>9} € {str(a.get('surfaceArea'))[:6]:>6} m²")


def main() -> None:
    candidates = step_a_discover_zone_id()
    step_b_test_zone_ids(candidates)
    step_c_bbox()
    print("\n" + "=" * 70)
    print("Cible : un filtre avec total bas (<5000) ET dépt 57 majoritaire.")
    print("Colle toute la sortie.")


if __name__ == "__main__":
    main()
