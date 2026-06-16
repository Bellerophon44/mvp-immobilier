"""Gazetteer unique des quartiers de Metz (issue #100, chantier B).

Source UNIQUE backend du vocabulaire et des donnees curatees par quartier. Les
referentiels historiquement dupliques en derivent par fonctions pures calculees
a l'import (sans lookup base, sans I/O) :
  - `metz_local._PROFILES` / `_DIST_KM` / `_ALIASES` ;
  - `market_stats._DISTRICT_TO_SECTOR` / `_SECTOR_DISTRICTS` ;
  - la partie quartiers de `scrapers.base._KNOWN_LOCALITIES` ;
  - la projection front `frontend/lib/districts.ts` (verrouillee par test).

Module Python de donnees (pas de JSON/YAML) : importable directement, type, sans
etape de chargement faillible sur le chemin `/analyze` (spec §2 Q1).

B est un REFACTOR PUR : toutes les valeurs reprennent a l'identique l'etat
historique (goldens captures avant migration), a la seule exception de
l'harmonisation Q6 du secteur de Sainte-Therese (`sector_display` accentue).

Cle canonique = sortie de `canonical_city` appliquee au libelle (invariant pivot
spec §3.0). `canonical_district` / `canonical_city` ne sont PAS reimplementees
ici : la derivation les APPELLE (risque ingestion, spec §5 / AC9).

Trou de couverture documente (lot ulterieur, hors B) : les quartiers
Ancienne-Ville et Les-Iles (Les Îles) sont presents dans `_PROFILES`, dans les
secteurs (`_SECTOR_DISTRICTS["Centre Ville"]`) et dans `METZ_DISTRICTS`
(selecteur front), MAIS leurs `aliases_text` sont volontairement vides : ils ne
sont donc PAS reconnus par l'extraction texte (`extract_district` /
`_KNOWN_LOCALITIES`). Etendre cette couverture changerait le comportement (ce ne
serait plus un refactor pur) -> correction renvoyee a un lot ulterieur, hors B.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from scrapers.base import canonical_city, canonical_district


@dataclass(frozen=True)
class GazetteerEntry:
    """Une entree de quartier de Metz.

    `aliases_text` : formes lower-case (accents conserves + variantes sans accent)
    matchees en substring par l'extraction texte. Vide = quartier non reconnu par
    le texte (trou de couverture documente, ex. Ancienne-Ville / Les-Iles).
    `aliases_canon` : cles canoniques de variantes/pieges (« / », libelles
    composes) -> `_ALIASES`.
    Les libelles bruts de STOCK rattaches au SECTEUR (ex. 'Vallières-lès-Bordes'
    -> 'Vallieres-Les-Bordes', 'Patrotte-Metz-Nord', forme composee
    'Plantières - Queuleu') sont modelises dans `_SECTORS` (composition ordonnee
    des secteurs), pas ici : ce ne sont JAMAIS des quartiers du selecteur.
    `centroid` : None partout en B (geocodage = chantier C).
    """

    canonical_key: str
    display_label: str
    aliases_text: List[str]
    aliases_canon: List[str]
    sector_key: str
    sector_display: str
    profile: Dict[str, str]
    dist_km: Dict[str, float]
    in_selector: bool
    commune: str = "Metz"
    postal_code: Optional[str] = None
    centroid: Optional[Tuple[float, float]] = None


# Ordre des entrees = ordre des formes derivees de quartiers dans
# `_KNOWN_LOCALITIES` (long-avant-court par construction des aliases_text). Les
# entrees sans aliases_text (Ancienne-Ville, Les-Iles) n'apparaissent pas dans
# l'extraction texte (trou de couverture, cf. docstring de module).
_ENTRIES: List[GazetteerEntry] = [
    GazetteerEntry(
        canonical_key="Devant-Les-Ponts",
        display_label="Devant-les-Ponts",
        aliases_text=["devant-les-ponts"],
        aliases_canon=[],
        sector_key="Devant-Les-Ponts",
        sector_display="Devant-les-Ponts",
        profile={
            "center": "~2 km au nord-ouest",
            "gare": "~2,5 km",
            "caractere": "Quartier nord-ouest résidentiel, proche de la Moselle.",
        },
        dist_km={"center": 2.0, "gare": 2.5},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Grange-Aux-Bois",
        display_label="Grange-aux-Bois",
        aliases_text=["grange-aux-bois"],
        aliases_canon=[],
        sector_key="Borny",
        sector_display="Borny",
        profile={
            "center": "~6 km à l'est",
            "gare": "~6 km",
            "caractere": "Quartier pavillonnaire récent à l'est, au calme.",
        },
        dist_km={"center": 6.0, "gare": 6.0},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Sainte-Therese",
        display_label="Sainte-Thérèse",
        aliases_text=["sainte-thérèse", "sainte-therese"],
        # Piege « / » : canonical_district ne split que sur « - », donc
        # « Sainte-Thérèse / Botanique » produit cette cle litterale -> remap.
        aliases_canon=["Sainte-Therese-/-Botanique"],
        # Harmonisation Q6 : cle canonique + libelle accentue (seul changement
        # voulu de B ; invisible utilisateur, secteur mono-quartier).
        sector_key="Sainte-Therese",
        sector_display="Sainte-Thérèse",
        profile={
            "center": "~2 km au sud",
            "gare": "~1,4 km",
            "caractere": "Petit quartier résidentiel sud, contigu au Sablon.",
        },
        dist_km={"center": 2.0, "gare": 1.4},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Nouvelle-Ville",
        display_label="Nouvelle Ville",
        aliases_text=["nouvelle ville"],
        aliases_canon=[],
        sector_key="Centre-Ville",
        sector_display="Centre Ville",
        profile={
            "center": "~1 km du centre",
            "gare": "immédiate (~0,3 km)",
            "caractere": "Quartier Impérial autour de la gare, architecture germanique.",
        },
        dist_km={"center": 1.0, "gare": 0.3},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Plantieres",
        display_label="Plantières",
        aliases_text=["plantières", "plantieres"],
        aliases_canon=["Plantieres-Queuleu"],
        sector_key="Plantieres-Queuleu",
        sector_display="Plantières-Queuleu",
        profile={
            "center": "~2,5 km à l'est",
            "gare": "~2,5 km",
            "caractere": "Résidentiel, mixité de pavillons et d'immeubles.",
        },
        dist_km={"center": 2.5, "gare": 2.5},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Bellecroix",
        display_label="Bellecroix",
        aliases_text=["bellecroix"],
        aliases_canon=[],
        sector_key="Bellecroix-Vallieres",
        sector_display="Bellecroix - Vallières",
        profile={
            "center": "~2,5 km à l'est",
            "gare": "~2,8 km",
            "caractere": "Plateau à l'est (fort de Bellecroix), quelques vues dégagées.",
        },
        dist_km={"center": 2.5, "gare": 2.8},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Vallieres",
        display_label="Vallières",
        aliases_text=["vallières", "vallieres"],
        aliases_canon=[],
        sector_key="Bellecroix-Vallieres",
        sector_display="Bellecroix - Vallières",
        profile={
            "center": "~4 km à l'est",
            "gare": "~4 km",
            "caractere": "Ancien village à l'est, dominante pavillonnaire.",
        },
        dist_km={"center": 4.0, "gare": 4.0},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="La-Patrotte",
        display_label="La Patrotte",
        aliases_text=["la patrotte"],
        aliases_canon=[],
        sector_key="Patrotte-Metz-Nord",
        sector_display="Patrotte-Metz-Nord",
        profile={
            "center": "~2,5 km au nord",
            "gare": "~3 km",
            "caractere": "Secteur nord populaire, en mutation.",
        },
        dist_km={"center": 2.5, "gare": 3.0},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Outre-Seille",
        display_label="Outre-Seille",
        aliases_text=["outre-seille"],
        aliases_canon=[],
        sector_key="Centre-Ville",
        sector_display="Centre Ville",
        profile={
            "center": "accolé au centre (~0,8 km)",
            "gare": "~1,3 km",
            "caractere": "Quartier historique vivant, jouxte l'hypercentre à l'est.",
        },
        dist_km={"center": 0.8, "gare": 1.3},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Technopole",
        display_label="Technopôle",
        aliases_text=["technopôle", "technopole"],
        aliases_canon=[],
        sector_key="Borny",
        sector_display="Borny",
        profile={
            "center": "~3,5 km au sud-est",
            "gare": "~3 km",
            "caractere": "Pôle tertiaire et universitaire, peu résidentiel.",
        },
        dist_km={"center": 3.5, "gare": 3.0},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Queuleu",
        display_label="Queuleu",
        aliases_text=["queuleu"],
        aliases_canon=["Queuleu-Plantieres"],
        sector_key="Plantieres-Queuleu",
        sector_display="Plantières-Queuleu",
        profile={
            "center": "~3 km au sud-est",
            "gare": "~2,5 km",
            "caractere": "Résidentiel pavillonnaire prisé et calme.",
        },
        dist_km={"center": 3.0, "gare": 2.5},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Sablon",
        display_label="Sablon",
        aliases_text=["sablon"],
        aliases_canon=[],
        sector_key="Sablon",
        sector_display="Sablon",
        profile={
            "center": "~1,8 km au sud",
            "gare": "~1,2 km",
            "caractere": "Quartier résidentiel familial au sud, proche gare.",
        },
        dist_km={"center": 1.8, "gare": 1.2},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Magny",
        display_label="Magny",
        aliases_text=["magny"],
        aliases_canon=[],
        sector_key="Magny",
        sector_display="Magny",
        profile={
            "center": "~5 km au sud",
            "gare": "~4,5 km",
            "caractere": "Secteur sud pavillonnaire, ambiance semi-résidentielle.",
        },
        dist_km={"center": 5.0, "gare": 4.5},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Borny",
        display_label="Borny",
        aliases_text=["borny"],
        aliases_canon=[],
        sector_key="Borny",
        sector_display="Borny",
        profile={
            "center": "~4,5 km à l'est",
            "gare": "~4,5 km",
            "caractere": "Grand quartier est, secteur en rénovation urbaine.",
        },
        dist_km={"center": 4.5, "gare": 4.5},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Centre-Ville",
        display_label="Centre-Ville",
        aliases_text=["centre-ville", "centre"],
        aliases_canon=["Centre"],
        sector_key="Centre-Ville",
        sector_display="Centre Ville",
        profile={
            "center": "cœur du centre (cathédrale à quelques pas)",
            "gare": "~0,8 km (≈ 10 min à pied)",
            "caractere": "Hypercentre historique et commerçant, le plus recherché.",
        },
        dist_km={"center": 0.2, "gare": 0.8},
        in_selector=True,
    ),
    # --- Entrees sans aliases_text : trou de couverture documente (hors B) ---
    GazetteerEntry(
        canonical_key="Ancienne-Ville",
        display_label="Ancienne Ville",
        aliases_text=[],
        aliases_canon=[],
        sector_key="Centre-Ville",
        sector_display="Centre Ville",
        profile={
            "center": "dans le centre historique",
            "gare": "~1 km",
            "caractere": "Vieille ville pavée autour de la colline Sainte-Croix.",
        },
        dist_km={"center": 0.4, "gare": 1.0},
        in_selector=True,
    ),
    GazetteerEntry(
        canonical_key="Les-Iles",
        display_label="Les Îles",
        aliases_text=[],
        aliases_canon=["Iles", "Ile"],
        sector_key="Centre-Ville",
        sector_display="Centre Ville",
        profile={
            "center": "~1 km du centre",
            "gare": "~1,8 km",
            "caractere": "Quartier sur la Moselle (plan d'eau, lac Symphonie), prisé.",
        },
        dist_km={"center": 1.0, "gare": 1.8},
        in_selector=True,
    ),
]


GAZETTEER: Dict[str, GazetteerEntry] = {e.canonical_key: e for e in _ENTRIES}


# Composition ORDONNEE des secteurs (reproduit l'ancien `_SECTORS_RAW`,
# market_stats.py). Cle = `sector_key` canonique ; valeur = (`sector_display`,
# libelles bruts dans l'ordre exact de declaration). L'ordre des secteurs ET
# l'ordre des quartiers dans chaque secteur sont figes ici pour reproduire a
# l'identique les maps secteur (golden 4) ; les libelles bruts sont canonicalises
# au chargement (`build_sector_maps`). Coherence avec les entrees : chaque libelle
# brut canonicalise est soit un `canonical_key` d'entree, soit une forme de STOCK
# (declaree en `aliases_stock_sector` sur l'entree du meme secteur), jamais un
# quartier du selecteur a part entiere.
_SECTORS: List[Tuple[str, str, List[str]]] = [
    ("Devant-Les-Ponts", "Devant-les-Ponts", ["Devant-les-Ponts"]),
    ("Patrotte-Metz-Nord", "Patrotte-Metz-Nord", ["Patrotte-Metz-Nord", "La Patrotte"]),
    ("Sablon", "Sablon", ["Sablon"]),
    ("Sainte-Therese", "Sainte-Thérèse", ["Sainte-Thérèse"]),
    ("Plantieres-Queuleu", "Plantières-Queuleu", ["Plantières - Queuleu", "Queuleu", "Plantières"]),
    ("Magny", "Magny", ["Magny"]),
    ("Borny", "Borny", ["Borny", "Technopôle", "Grange-aux-Bois"]),
    ("Bellecroix-Vallieres", "Bellecroix - Vallières", ["Bellecroix", "Vallières-lès-Bordes", "Vallières"]),
    ("Centre-Ville", "Centre Ville", ["Centre-Ville", "Ancienne-Ville", "Nouvelle Ville", "Les Îles", "Outre-Seille"]),
]


# ===========================================================================
# Fonctions de derivation pures (calculees a l'import par les consommateurs).
# ===========================================================================

def profiles() -> Dict[str, Dict[str, str]]:
    """`_PROFILES` : {canonical_key: {name, center, gare, caractere}}."""
    return {
        e.canonical_key: {"name": e.display_label, **e.profile}
        for e in GAZETTEER.values()
    }


def dist_km() -> Dict[str, Dict[str, float]]:
    """`_DIST_KM` : {canonical_key: {center, gare}}. Memes cles que profiles()
    par construction (profile ET dist_km sont deux champs de la meme entree)."""
    return {e.canonical_key: dict(e.dist_km) for e in GAZETTEER.values()}


def aliases() -> Dict[str, str]:
    """`_ALIASES` : union des aliases_canon -> canonical_key."""
    out: Dict[str, str] = {}
    for e in GAZETTEER.values():
        for alias in e.aliases_canon:
            out[alias] = e.canonical_key
    return out


def known_localities_districts() -> List[str]:
    """Formes lower-case de quartiers pour `_KNOWN_LOCALITIES`, ordonnees
    long-avant-court (consigne base.py : libelles longs avant courts pour le
    substring match). L'ordre des entrees + l'ordre intra-entree des aliases_text
    placent deja les formes longues avant les courtes ; on stabilise par un tri
    par longueur decroissante (stable) pour garantir l'invariant AC1."""
    forms: List[str] = []
    for e in GAZETTEER.values():
        forms.extend(e.aliases_text)
    forms.sort(key=len, reverse=True)
    return forms


def sectors_raw() -> Dict[str, List[str]]:
    """`_SECTORS_RAW` historique : {sector_key (canonique): [libelles bruts]}.

    La cle est la forme CANONIQUE du secteur (`sector_key`) — un consommateur
    referençant le secteur de Sainte-Therese par la cle pivot 'Sainte-Therese'
    (issue #100 chantier A) la retrouve. Les valeurs sont les libelles bruts
    (canonicalises au chargement par `build_sector_maps`)."""
    return {sector_key: list(raw_labels) for sector_key, _disp, raw_labels in _SECTORS}


def build_sector_maps():
    """Maps secteur derivees, reproduisant `market_stats._build_sector_maps` :
      - `_DISTRICT_TO_SECTOR[canonical_key] = sector_display`
      - `_SECTOR_DISTRICTS[sector_display] = [canonical_key, ...]`
    Iteration sur `_SECTORS` (ordre fige reproduisant `_SECTORS_RAW`), libelles
    bruts canonicalises via `canonical_district` au chargement (golden 4)."""
    district_to_sector: Dict[str, str] = {}
    sector_districts: Dict[str, List[str]] = {}
    for _sector_key, sector_display, raw_labels in _SECTORS:
        canon: List[str] = []
        for raw in raw_labels:
            cq = canonical_district(raw, "Metz")
            if cq and cq not in canon:
                canon.append(cq)
                district_to_sector[cq] = sector_display
        sector_districts[sector_display] = canon
    return district_to_sector, sector_districts


def selector_labels() -> List[str]:
    """`display_label` des entrees `in_selector == True` (projection front)."""
    return [e.display_label for e in GAZETTEER.values() if e.in_selector]
