"""Profil local de quartier (couche A du chantier "Ancrage local").

Données *curatées, déterministes et factuelles* sur les quartiers de Metz, sans
géocodage : on reste au niveau du quartier (centroïde), donc les distances sont
volontairement **approximatives** ("~", "environ") pour ne pas créer de fausse
précision. Ce bloc est affiché en "Contexte local" **non-scoré** : il informe,
il n'entre pas dans le score 40/30/30.

La couche B (contrôle de cohérence des allégations de l'annonce) et la couche C
(géocodage adresse -> distances exactes) viendront s'appuyer sur ces profils.
"""

from typing import Any, Dict, List, Optional

from scrapers.base import canonical_city, canonical_district


# Attrait frontalier : commun à tout Metz (axe A31 plein nord vers le sillon
# lorrain et le Luxembourg). Phrasé qualitatif, sans temps faussement précis.
_A31_LUXEMBOURG = (
    "Axe A31 vers le sillon lorrain ; Luxembourg accessible (~45 min hors "
    "trafic), bassin d'emploi frontalier très recherché."
)


# Clé = forme canonique (canonical_city) du quartier, pour matcher quelle que
# soit l'orthographe d'entrée. `name` = libellé affiché (accents conservés).
# `center` = distance approx. au centre / cathédrale St-Étienne. `gare` = gare
# Metz-Ville (le Centre Pompidou-Metz lui est accolé, d'où le regroupement).
_PROFILES: Dict[str, Dict[str, str]] = {
    "Centre-Ville": {
        "name": "Centre-Ville",
        "center": "cœur du centre (cathédrale à quelques pas)",
        "gare": "~0,8 km (≈ 10 min à pied)",
        "caractere": "Hypercentre historique et commerçant, le plus recherché.",
    },
    "Ancienne-Ville": {
        "name": "Ancienne Ville",
        "center": "dans le centre historique",
        "gare": "~1 km",
        "caractere": "Vieille ville pavée autour de la colline Sainte-Croix.",
    },
    "Nouvelle-Ville": {
        "name": "Nouvelle Ville",
        "center": "~1 km du centre",
        "gare": "immédiate (~0,3 km)",
        "caractere": "Quartier Impérial autour de la gare, architecture germanique.",
    },
    "Les-Iles": {
        "name": "Les Îles",
        "center": "~1 km du centre",
        "gare": "~1,8 km",
        "caractere": "Quartier sur la Moselle (plan d'eau, lac Symphonie), prisé.",
    },
    "Outre-Seille": {
        "name": "Outre-Seille",
        "center": "accolé au centre (~0,8 km)",
        "gare": "~1,3 km",
        "caractere": "Quartier historique vivant, jouxte l'hypercentre à l'est.",
    },
    "Sablon": {
        "name": "Sablon",
        "center": "~1,8 km au sud",
        "gare": "~1,2 km",
        "caractere": "Quartier résidentiel familial au sud, proche gare.",
    },
    "Queuleu": {
        "name": "Queuleu",
        "center": "~3 km au sud-est",
        "gare": "~2,5 km",
        "caractere": "Résidentiel pavillonnaire prisé et calme.",
    },
    "Plantieres": {
        "name": "Plantières",
        "center": "~2,5 km à l'est",
        "gare": "~2,5 km",
        "caractere": "Résidentiel, mixité de pavillons et d'immeubles.",
    },
    "Bellecroix": {
        "name": "Bellecroix",
        "center": "~2,5 km à l'est",
        "gare": "~2,8 km",
        "caractere": "Plateau à l'est (fort de Bellecroix), quelques vues dégagées.",
    },
    "Borny": {
        "name": "Borny",
        "center": "~4,5 km à l'est",
        "gare": "~4,5 km",
        "caractere": "Grand quartier est, secteur en rénovation urbaine.",
    },
    "Magny": {
        "name": "Magny",
        "center": "~5 km au sud",
        "gare": "~4,5 km",
        "caractere": "Secteur sud pavillonnaire, ambiance semi-résidentielle.",
    },
    "Vallieres": {
        "name": "Vallières",
        "center": "~4 km à l'est",
        "gare": "~4 km",
        "caractere": "Ancien village à l'est, dominante pavillonnaire.",
    },
    "Devant-Les-Ponts": {
        "name": "Devant-les-Ponts",
        "center": "~2 km au nord-ouest",
        "gare": "~2,5 km",
        "caractere": "Quartier nord-ouest résidentiel, proche de la Moselle.",
    },
    "La-Patrotte": {
        "name": "La Patrotte",
        "center": "~2,5 km au nord",
        "gare": "~3 km",
        "caractere": "Secteur nord populaire, en mutation.",
    },
    "Grange-Aux-Bois": {
        "name": "Grange-aux-Bois",
        "center": "~6 km à l'est",
        "gare": "~6 km",
        "caractere": "Quartier pavillonnaire récent à l'est, au calme.",
    },
    "Technopole": {
        "name": "Technopôle",
        "center": "~3,5 km au sud-est",
        "gare": "~3 km",
        "caractere": "Pôle tertiaire et universitaire, peu résidentiel.",
    },
}


# Variantes d'écriture / libellés composés -> clé canonique d'un profil existant.
_ALIASES: Dict[str, str] = {
    "Centre": "Centre-Ville",
    "Plantieres-Queuleu": "Plantieres",
    "Queuleu-Plantieres": "Queuleu",
    "Iles": "Les-Iles",
    "Ile": "Les-Iles",
}


def _resolve_key(district: Optional[str], city: Optional[str] = "Metz") -> Optional[str]:
    """Clé canonique d'un quartier de Metz, en tolérant le préfixe ville
    ('Metz - Sablon'), les accents et les libellés composés. None si inconnu."""
    if not district:
        return None
    key = canonical_district(district, city) or canonical_city(district)
    if not key:
        return None
    if key in _PROFILES:
        return key
    return _ALIASES.get(key)


def local_context(district: Optional[str], city: Optional[str] = "Metz") -> Optional[Dict[str, Any]]:
    """Bloc "Contexte local" non-scoré pour un quartier de Metz, ou None si le
    quartier n'est pas renseigné / reconnu (on n'affiche alors rien plutôt que
    d'inventer)."""
    key = _resolve_key(district, city)
    if not key:
        return None
    p = _PROFILES[key]
    facts: List[Dict[str, str]] = [
        {"label": "Centre / Cathédrale St-Étienne", "value": p["center"]},
        {"label": "Gare Metz-Ville · Centre Pompidou-Metz", "value": p["gare"]},
        {"label": "Axe A31 · Luxembourg", "value": _A31_LUXEMBOURG},
    ]
    return {
        "district": p["name"],
        "summary": p["caractere"],
        "facts": facts,
    }
