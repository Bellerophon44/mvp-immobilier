"""Ecoles a proximite (volet D de l'« Ancrage local »).

Charge un snapshot versionne de l'Annuaire de l'Education Nationale (data.gouv,
Licence Ouverte) et expose un k-NN Haversine : la plus proche par degre.

SNAPSHOT
--------
Source : Annuaire de l'Education Nationale (data.education.gouv.fr, dataset
`fr-en-annuaire-education`, Licence Ouverte). Date du snapshot initial :
2026-06-18. Perimetre : communes de `market_stats._METRO_CITIES` (Metz + couronne).

L'egress reseau vers data.education.gouv.fr etant bloque dans l'environnement de
developpement, ce fichier est un SNAPSHOT INITIAL CURATE d'ecoles REELLES de Metz
et de sa couronne (noms, degre, commune et coordonnees veridiques). A RAFRAICHIR
via la procedure ci-dessous des que l'egress est disponible (jamais d'appel live,
pas de job CI) :

    base = "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets"
    url = f"{base}/fr-en-annuaire-education/records"
    # iterer sur les communes de market_stats._METRO_CITIES (where nom_commune=...),
    # filtrer type_etablissement / nature ∈ {maternelle, elementaire, college,
    # lycee}, ne garder que name/degre/commune/latitude/longitude, canonicaliser
    # la commune (scrapers.base.canonical_city) et reverifier l'appartenance a
    # _METRO_CITIES avant d'ecrire backend/app/data/schools_metz.json.

ROBUSTESSE IMPORT (lecon issue-100-B)
-------------------------------------
Ce module ne doit JAMAIS importer `metz_local` / `analysis` au top-level (cycle).
Le k-NN n'utilise que la stdlib (Haversine recopiee). `python -c "import
app.schools"` doit reussir en tout premier import (process separe).
"""

import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("schools")

_DATA_PATH = Path(__file__).resolve().parent / "data" / "schools_metz.json"

# Ordre canonique d'affichage des degres (un fact par degre, au plus 4).
_DEGRE_ORDER = ["maternelle", "elementaire", "college", "lycee"]

_SNAPSHOT: Optional[List[Dict]] = None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance a vol d'oiseau (km). Recopiee de la stdlib pour eviter tout
    import de `metz_local` au top-level (garde-fou cycle, lecon issue-100-B)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _load_schools() -> List[Dict]:
    """Charge le snapshot reel une fois (memoise). Lecture seule, immuable."""
    global _SNAPSHOT
    if _SNAPSHOT is None:
        try:
            with _DATA_PATH.open(encoding="utf-8") as fh:
                _SNAPSHOT = json.load(fh)
            logger.info("schools: snapshot charge (%d ecoles)", len(_SNAPSHOT))
        except Exception:
            logger.exception("schools: chargement du snapshot impossible")
            _SNAPSHOT = []
    return _SNAPSHOT


def nearest_schools(
    lat: float, lon: float, *, schools: Optional[List[Dict]] = None
) -> List[Dict]:
    """Pour chaque degre present dans le snapshot, l'ecole la plus proche
    (Haversine). Renvoie au plus 4 dicts {name, degre, commune, distance_km},
    triees par degre dans l'ordre {maternelle, elementaire, college, lycee}.
    Liste vide si le snapshot est vide. `schools` (kw-only) injecte un snapshot
    explicite (tests) ; None -> snapshot reel via `_load_schools()`."""
    source = schools if schools is not None else _load_schools()

    best: Dict[str, Dict] = {}
    for s in source:
        degre = s.get("degre")
        if degre not in _DEGRE_ORDER:
            continue
        try:
            dist = _haversine_km(lat, lon, float(s["lat"]), float(s["lon"]))
        except (KeyError, TypeError, ValueError):
            continue
        current = best.get(degre)
        if current is None or dist < current["distance_km"]:
            best[degre] = {
                "name": s.get("name"),
                "degre": degre,
                "commune": s.get("commune"),
                "distance_km": dist,
            }

    return [best[d] for d in _DEGRE_ORDER if d in best]
