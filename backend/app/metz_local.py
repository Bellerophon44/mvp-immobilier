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
import math

from scrapers.base import canonical_city, canonical_district
from app import geo_gazetteer as gazetteer


# Attrait frontalier : commun à tout Metz (axe A31 plein nord vers le sillon
# lorrain et le Luxembourg). Phrasé qualitatif, sans temps faussement précis.
_A31_LUXEMBOURG = (
    "Axe A31 vers le sillon lorrain ; Luxembourg accessible (~45 min hors "
    "trafic), bassin d'emploi frontalier très recherché."
)


# Coordonnées (lat, lon) curatées des points d'intérêt servant au géocodage
# (couche C). Constantes, vérifiables sur une carte. L'échangeur A31 est le point
# d'accès autoroutier le plus proche de Metz (valeur approchée, l'A31 longe la
# ville à l'ouest).
_POI: Dict[str, tuple] = {
    "cathedrale": (49.1203, 6.1758),   # Cathédrale Saint-Étienne
    "pompidou": (49.1095, 6.1825),     # Centre Pompidou-Metz
    "gare": (49.1097, 6.1773),         # Gare de Metz-Ville
    "a31": (49.1107, 6.1305),          # Échangeur A31 le plus proche (approx.)
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance à vol d'oiseau (km) entre deux points GPS (formule de Haversine).

    Limite connue : c'est une distance en ligne droite, pas un temps de trajet à
    pied ou en voiture (cf. CLAUDE.md §11 — optimisation routing à venir)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _fmt_dist(km: float) -> str:
    """'~420 m' sous 1 km, sinon '~1,2 km' (une décimale) — précision au point
    géocodé, plus fine que l'arrondi au demi-km du mode quartier."""
    if km < 1.0:
        return f"~{int(round(km * 1000 / 10) * 10)} m"
    return f"~{km:.1f}".replace(".", ",") + " km"


# Clé = forme canonique (canonical_city) du quartier, pour matcher quelle que
# soit l'orthographe d'entrée. `name` = libellé affiché (accents conservés).
# `center` = distance approx. au centre / cathédrale St-Étienne. `gare` = gare
# Metz-Ville (le Centre Pompidou-Metz lui est accolé, d'où le regroupement).
# DERIVE de la source unique `app.geo_gazetteer` (issue #100 chantier B) : valeurs
# curatees identiques, plus de duplication. `_PROFILES` et `_DIST_KM` partagent le
# meme jeu de cles par construction (deux champs de la meme entree gazetteer).
_PROFILES: Dict[str, Dict[str, str]] = gazetteer.profiles()


# Distances numériques approximatives (km) au niveau du quartier, pour le
# contrôle de cohérence des allégations (couche B). center = centre / cathédrale
# St-Étienne ; gare = gare Metz-Ville (Pompidou accolé). Volontairement grossières
# (centroïde de quartier) : servent à juger le plausible, pas à mesurer.
_DIST_KM: Dict[str, Dict[str, float]] = gazetteer.dist_km()


# Variantes d'écriture / libellés composés -> clé canonique d'un profil existant.
# Inclut le piège « / » (« Sainte-Thérèse / Botanique »). DERIVE du gazetteer.
_ALIASES: Dict[str, str] = gazetteer.aliases()


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


# Réserve C2 (garde-fou « confiant mais faux ») : quartier forcé par
# l'utilisateur mais non confirmé par l'annonce. Wording stable (substring
# « non confirmé » verrouillé par les tests).
_DISTRICT_CAVEAT = "Quartier indiqué par vous, non confirmé par l'annonce."


def local_context(
    district: Optional[str],
    city: Optional[str] = "Metz",
    district_corroborated: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """Bloc "Contexte local" non-scoré pour un quartier de Metz, ou None si le
    quartier n'est pas renseigné / reconnu (on n'affiche alors rien plutôt que
    d'inventer).

    `district_corroborated` (garde-fou C2) : None/True -> comportement inchangé ;
    False -> on ajoute la réserve `district_caveat` (override non confirmé par
    l'annonce)."""
    key = _resolve_key(district, city)
    if not key:
        return None
    p = _PROFILES[key]
    facts: List[Dict[str, str]] = [
        {"label": "Centre / Cathédrale St-Étienne", "value": p["center"]},
        {"label": "Gare Metz-Ville · Centre Pompidou-Metz", "value": p["gare"]},
        {"label": "Axe A31 · Luxembourg", "value": _A31_LUXEMBOURG},
    ]
    ctx: Dict[str, Any] = {
        "district": p["name"],
        "summary": p["caractere"],
        "facts": facts,
        "precision": "quartier",
    }
    if district_corroborated is False:
        ctx["district_caveat"] = _DISTRICT_CAVEAT
    return ctx


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
    dist_override: Optional[Dict[str, float]] = None,
    district_corroborated: Optional[bool] = None,
) -> List[Dict[str, str]]:
    """Confronte les allégations locales de l'annonce (couche B) aux distances de
    référence : `dist_override` (distances exactes issues du géocodage, couche C)
    si fourni, sinon le profil curaté du quartier. Retourne [] si l'on n'a ni
    quartier reconnu ni distances, ou s'il n'y a aucune allégation.

    `district_corroborated` (garde-fou C2) : None/True -> comportement inchangé ;
    False -> tout claim qui serait sinon `coherent` est rétrogradé `a_verifier`
    (on n'affirme pas une cohérence locale sur un quartier que l'annonce ne
    confirme pas)."""
    key = _resolve_key(district, city)
    if (not key and not dist_override) or not claims:
        return []
    name = _PROFILES[key]["name"] if key else "Le bien"
    dist = dist_override or _DIST_KM.get(key, {"center": 0.0, "gare": 0.0})
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
        if district_corroborated is False and status == COHERENT:
            status = A_VERIFIER
            note = (
                "Quartier non confirmé par l'annonce : cohérence à vérifier "
                "(le profil affiché correspond au quartier que vous avez indiqué)."
            )
        out.append({"text": text, "type": ctype, "status": status, "note": note})
    return out


def precise_distances_km(lat: float, lon: float) -> Dict[str, float]:
    """Distances exactes (km, à vol d'oiseau) du bien aux POI curatés."""
    return {poi: haversine_km(lat, lon, c[0], c[1]) for poi, c in _POI.items()}


def claim_distances_from_coords(lat: float, lon: float) -> Dict[str, float]:
    """Distances {center, gare} pour le contrôle de cohérence (couche B) à partir
    des coordonnées exactes : centre = cathédrale, gare = gare Metz-Ville."""
    d = precise_distances_km(lat, lon)
    return {"center": d["cathedrale"], "gare": d["gare"]}


def local_context_from_coords(
    lat: float,
    lon: float,
    district: Optional[str] = None,
    city: Optional[str] = "Metz",
    address: Optional[str] = None,
) -> Dict[str, Any]:
    """Bloc « Contexte local » bâti sur les distances EXACTES au point géocodé
    (couche C). Conserve le nom / caractère du quartier quand il est reconnu, mais
    remplace les distances approximatives par des mesures au bien près."""
    d = precise_distances_km(lat, lon)
    key = _resolve_key(district, city)
    profile = _PROFILES.get(key) if key else None

    gare_pompidou = min(d["gare"], d["pompidou"])
    facts: List[Dict[str, str]] = [
        {"label": "Centre / Cathédrale St-Étienne", "value": _fmt_dist(d["cathedrale"])},
        {"label": "Gare Metz-Ville · Centre Pompidou-Metz", "value": _fmt_dist(gare_pompidou)},
        {"label": "Échangeur A31 le plus proche", "value": f"{_fmt_dist(d['a31'])} · {_A31_LUXEMBOURG}"},
    ]
    ctx: Dict[str, Any] = {
        "district": profile["name"] if profile else "Metz",
        "summary": profile["caractere"] if profile else "Localisation précise (adresse géocodée).",
        "facts": facts,
        "precision": "adresse",
    }
    if address:
        ctx["address"] = address
    return ctx
