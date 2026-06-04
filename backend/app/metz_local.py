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


# Distances numériques approximatives (km) au niveau du quartier, pour le
# contrôle de cohérence des allégations (couche B). center = centre / cathédrale
# St-Étienne ; gare = gare Metz-Ville (Pompidou accolé). Volontairement grossières
# (centroïde de quartier) : servent à juger le plausible, pas à mesurer.
_DIST_KM: Dict[str, Dict[str, float]] = {
    "Centre-Ville": {"center": 0.2, "gare": 0.8},
    "Ancienne-Ville": {"center": 0.4, "gare": 1.0},
    "Nouvelle-Ville": {"center": 1.0, "gare": 0.3},
    "Les-Iles": {"center": 1.0, "gare": 1.8},
    "Outre-Seille": {"center": 0.8, "gare": 1.3},
    "Sablon": {"center": 1.8, "gare": 1.2},
    "Queuleu": {"center": 3.0, "gare": 2.5},
    "Plantieres": {"center": 2.5, "gare": 2.5},
    "Bellecroix": {"center": 2.5, "gare": 2.8},
    "Borny": {"center": 4.5, "gare": 4.5},
    "Magny": {"center": 5.0, "gare": 4.5},
    "Vallieres": {"center": 4.0, "gare": 4.0},
    "Devant-Les-Ponts": {"center": 2.0, "gare": 2.5},
    "La-Patrotte": {"center": 2.5, "gare": 3.0},
    "Grange-Aux-Bois": {"center": 6.0, "gare": 6.0},
    "Technopole": {"center": 3.5, "gare": 3.0},
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


# Statuts de cohérence d'une allégation locale (couche B).
COHERENT = "coherent"
A_VERIFIER = "a_verifier"
PEU_PLAUSIBLE = "peu_plausible"


def _km(value: float) -> str:
    """Distance arrondie au demi-km, en notation française ('4,5', '2')."""
    rounded = round(value * 2) / 2
    text = f"{rounded:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _assess_distance(km: float, near: float, far: float) -> str:
    """Cohérent si <= near, peu plausible si > far, à vérifier entre les deux."""
    if km <= near:
        return COHERENT
    if km > far:
        return PEU_PLAUSIBLE
    return A_VERIFIER


def _assess_one(ctype: str, name: str, dist: Dict[str, float]) -> tuple:
    """(status, note) pour une allégation, confrontée au profil du quartier.

    Règle de prudence : on ne contredit que ce que la géographie de quartier rend
    réellement douteux ; le reste (commerces, calme, écoles…) n'est pas vérifiable
    depuis le profil -> 'à vérifier' neutre, jamais 'cohérent' par complaisance.
    """
    center = dist.get("center")
    gare = dist.get("gare")

    if ctype == "cathedrale":
        status = _assess_distance(center, 1.0, 2.5)
        if status == PEU_PLAUSIBLE:
            return status, f"{name} est à ~{_km(center)} km du centre : une vue / proximité directe de la cathédrale est peu probable."
        if status == A_VERIFIER:
            return status, f"{name} n'est pas dans l'hypercentre : proximité de la cathédrale à confirmer."
        return status, f"Cohérent : {name} est au cœur du centre."

    if ctype == "centre":
        status = _assess_distance(center, 1.5, 3.0)
        if status == PEU_PLAUSIBLE:
            return status, f"{name} est à ~{_km(center)} km du centre : « proche centre » est optimiste."
        if status == A_VERIFIER:
            return status, f"{name} est à distance intermédiaire du centre : à nuancer."
        return status, f"Cohérent : {name} est proche du centre."

    if ctype == "gare":
        status = _assess_distance(gare, 1.2, 2.5)
        if status == PEU_PLAUSIBLE:
            return status, f"Gare à ~{_km(gare)} km de {name} : « proche gare » est peu plausible à pied."
        if status == A_VERIFIER:
            return status, f"Gare à ~{_km(gare)} km de {name} : proximité à confirmer (à pied vs en transport)."
        return status, f"Cohérent : la gare est proche de {name}."

    if ctype == "a31":
        return COHERENT, "Cohérent : tout Metz est relié à l'A31 (axe vers le Luxembourg, bassin frontalier)."

    # transport / commerces / nature / ecoles / calme / autre : non vérifiable
    # depuis le profil de quartier.
    return A_VERIFIER, "Allégation non vérifiable depuis le profil de quartier — à confirmer sur place."


def assess_claims(
    district: Optional[str],
    claims: List[Dict[str, Any]],
    city: Optional[str] = "Metz",
) -> List[Dict[str, str]]:
    """Confronte les allégations locales de l'annonce (couche B) au profil curaté
    du quartier. Retourne [] si le quartier est inconnu (on ne peut rien affirmer)
    ou s'il n'y a aucune allégation."""
    key = _resolve_key(district, city)
    if not key or not claims:
        return []
    name = _PROFILES[key]["name"]
    dist = _DIST_KM.get(key, {"center": 0.0, "gare": 0.0})
    out: List[Dict[str, str]] = []
    for c in claims:
        if isinstance(c, dict):
            text = (c.get("text") or "").strip()
            ctype = c.get("type") or "autre"
        else:
            text, ctype = str(c).strip(), "autre"
        if not text:
            continue
        status, note = _assess_one(ctype, name, dist)
        out.append({"text": text, "type": ctype, "status": status, "note": note})
    return out
