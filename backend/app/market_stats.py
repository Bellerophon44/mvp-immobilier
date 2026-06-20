import logging

import numpy as np
from typing import Optional, Dict, Any, List

from db.session import SessionLocal
from db.models import Comparable
from scrapers.base import (
    canonical_city,
    canonical_district,
    construction_epoch,
    dpe_band,
    DPE_BANDS,
    dpe_rank,
)
from app import geo_gazetteer as gazetteer


logger = logging.getLogger("market_stats")


# Un filtre plus précis (quartier, bande DPE) n'est retenu que si son
# sous-échantillon reste assez fourni, sinon ses quartiles sont trompeurs : on
# retombe sur un périmètre plus large et plus robuste. Même seuil que la
# confiance "Élevée".
MIN_REFINED_COMPARABLES = 10
MIN_COMPARABLES = 5  # plancher absolu (niveau ville) ; <5 -> quartiles trop fragiles
MIN_PROFILE = 5      # mini pour calculer un profil DPE/année de pool fiable


# Metz Métropole : niveau AU-DESSUS de la ville, regroupant Metz et ses communes
# limitrophes. Filet le plus large de la cascade : une commune limitrophe trop
# creuse (ou Magny / un bien hors Metz-intra) peut y puiser des comparables
# observés plutôt que de retomber sur "Indéterminé". Toujours 100% observé.
_METRO_NAME = "Metz Métropole"
_METRO_CITIES_RAW = [
    "Metz",
    "Montigny-lès-Metz",
    "Le Ban-Saint-Martin",
    "Longeville-lès-Metz",
    "Saint-Julien-lès-Metz",
    "Scy-Chazelles",
    "Plappeville",
    "Lessy",
    "Woippy",
    "Marly",
    "Augny",
]
_METRO_CITIES = sorted({canonical_city(c) for c in _METRO_CITIES_RAW if canonical_city(c)})


# Secteurs de Metz : regroupements de quartiers adjacents. Quand un quartier est
# trop creux pour des quartiles fiables, on emprunte aux quartiers voisins du même
# secteur AVANT de retomber sur toute la ville — toujours 100% comparables
# observés, jamais d'estimation. DERIVE de la source unique `app.geo_gazetteer`
# (issue #100 chantier B) : `_DISTRICT_TO_SECTOR[canonical_key] = sector_display`,
# `_SECTOR_DISTRICTS[sector_display] = [canonical_key, ...]`. Les libellés bruts de
# stock (formes composées bien'ici, 'Vallières-lès-Bordes', 'Patrotte-Metz-Nord')
# sont canonicalisés au chargement, comme avant. Harmonisation Q6 : le secteur de
# Sainte-Thérèse expose désormais le libellé affiché accentué.
# `_SECTORS_RAW` (clé = sector_key canonique) reste exposé pour les consommateurs
# référençant un secteur par sa clé pivot (issue #100 chantier A, AC10).
_SECTORS_RAW = gazetteer.sectors_raw()
_DISTRICT_TO_SECTOR, _SECTOR_DISTRICTS = gazetteer.build_sector_maps()

# Table curatee des quartiers inter-communaux (chantier C1) :
# {canonical_key: tuple(communes canonicalisees)}. Derivee a l'import depuis la
# source unique `geo_gazetteer`. SEUL alimentateur de `cities` au niveau quartier
# de la cascade : un quartier absent de la table garde le filtre commune exact.
_INTERCOMMUNAL = gazetteer.intercommunal_districts()


# ============================
# Fonctions statistiques simples
# ============================

def _median(values):
    return float(np.median(values))


def _percentile(values, q):
    return float(np.percentile(values, q))


# ============================
# Récupération des comparables
# ============================

def _fetch_comparables(
    city: str,
    district: Optional[str],
    property_type: str,
    surface_min: float,
    surface_max: float,
    dpe_letters: Optional[set] = None,
    districts: Optional[List[str]] = None,
    cities: Optional[List[str]] = None,
):
    """Récupère les comparables selon des critères simples et explicables.

    `cities` (liste) filtre sur un ensemble de communes — utilisé pour le
    périmètre métropole ; `districts` (liste) sur un ensemble de quartiers
    (secteur) ; `district` (str) sur un seul quartier."""
    db = SessionLocal()
    try:
        query = db.query(Comparable).filter(
            Comparable.property_type == property_type,
            Comparable.surface_m2 >= surface_min,
            Comparable.surface_m2 <= surface_max,
        )
        if cities:
            query = query.filter(Comparable.city.in_(cities))
        else:
            query = query.filter(Comparable.city == city)
        if districts:
            query = query.filter(Comparable.district.in_(districts))
        elif district:
            query = query.filter(Comparable.district == district)
        if dpe_letters:
            query = query.filter(Comparable.dpe.in_(list(dpe_letters)))
        return query.all()
    finally:
        db.close()


def _pool_profile(comparables: List[Comparable]) -> Dict[str, Any]:
    """Profil du pool pour le signal explicatif : DPE médian et année médiane
    (calculés seulement si assez de données, sinon None)."""
    ranks = [r for c in comparables if (r := dpe_rank(c.dpe)) is not None]
    years = [c.construction_year for c in comparables if c.construction_year]
    pool_dpe = "ABCDEFG"[int(round(_median(ranks)))] if len(ranks) >= MIN_PROFILE else None
    pool_year = int(_median(years)) if len(years) >= MIN_PROFILE else None
    return {"pool_dpe": pool_dpe, "pool_year": pool_year}


# ============================
# Calcul des statistiques marché
# ============================

def compute_market_stats(
    city: str,
    district: Optional[str],
    property_type: str,
    surface_m2: float,
    dpe: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Statistiques du marché local observable, via une cascade qui retient le
    périmètre le plus précis encore suffisamment peuplé :
      quartier+DPE -> quartier -> secteur+DPE -> secteur -> ville+DPE -> ville
      -> métropole+DPE -> métropole.
    Le secteur (quartiers voisins) comble les quartiers creux, puis la métropole
    (communes limitrophes) comble les communes creuses, sans jamais estimer.
    Retourne None si même le périmètre le plus large est trop pauvre.
    """
    city = canonical_city(city)
    district = canonical_district(district, city)
    band = dpe_band(dpe)
    band_letters = DPE_BANDS.get(band) if band else None

    sector = _DISTRICT_TO_SECTOR.get(district) if district else None
    sector_districts = _SECTOR_DISTRICTS.get(sector) if sector else None
    # Quartier inter-communal : son pool quartier puise dans l'ENSEMBLE de ses
    # communes (table curatee) au lieu de la seule commune du bien. None sinon.
    district_cities = _INTERCOMMUNAL.get(district) if district else None
    # La métropole n'est mobilisée que si le bien est dans le périmètre Metz
    # Métropole (sinon on ne s'autorise pas à élargir à des communes étrangères).
    metro_cities = _METRO_CITIES if city in _METRO_CITIES else None

    surface_min = surface_m2 * 0.8
    surface_max = surface_m2 * 1.2

    # Niveaux candidats, du plus précis au plus large.
    # Chaque candidat : (scope, scope_name, district, districts, band, cities).
    # Le DERNIER candidat est le filet (accepté quel que soit le volume).
    candidates = []
    if district and band_letters:
        candidates.append(("quartier", district, district, None, band, district_cities))
    if district:
        candidates.append(("quartier", district, district, None, None, district_cities))
    if sector_districts and band_letters:
        candidates.append(("secteur", sector, None, sector_districts, band, None))
    if sector_districts:
        candidates.append(("secteur", sector, None, sector_districts, None, None))
    if band_letters:
        candidates.append(("ville", city, None, None, band, None))
    candidates.append(("ville", city, None, None, None, None))
    if metro_cities and band_letters:
        candidates.append(("metropole", _METRO_NAME, None, None, band, metro_cities))
    if metro_cities:
        candidates.append(("metropole", _METRO_NAME, None, None, None, metro_cities))

    chosen = None
    last_index = len(candidates) - 1
    for i, (scope, name, dist, dists, b, cities) in enumerate(candidates):
        comparables = _fetch_comparables(
            city, dist, property_type, surface_min, surface_max,
            DPE_BANDS.get(b) if b else None, districts=dists, cities=cities,
        )
        is_base = (i == last_index)
        # La ville (sans DPE) reste préférée dès qu'elle a le plancher absolu :
        # on n'élargit à la métropole que si la commune est réellement trop creuse,
        # pour ne pas diluer un pool communal exploitable.
        ville_usable = scope == "ville" and b is None and len(comparables) >= MIN_COMPARABLES
        if is_base or ville_usable or len(comparables) >= MIN_REFINED_COMPARABLES:
            chosen = (scope, name, b, comparables)
            break

    scope, scope_name, b, comparables = chosen
    logger.info(
        "market_stats: scope=%s name=%r dpe_band=%r -> %d comparables",
        scope, scope_name, b, len(comparables),
    )

    if len(comparables) < MIN_COMPARABLES:
        return None

    prices_m2 = [c.price_m2 for c in comparables]
    q1 = _percentile(prices_m2, 25)
    median = _median(prices_m2)
    q3 = _percentile(prices_m2, 75)

    return {
        "count": len(prices_m2),
        "median": median,
        "q1": q1,
        "q3": q3,
        "dispersion": q3 - q1,
        "scope": scope,
        "scope_name": scope_name,
        "dpe_band": b,
        **_pool_profile(comparables),
    }


# ============================
# Interprétation métier (pilier)
# ============================

def _scope_context(market_stats: Dict[str, Any]) -> str:
    scope = market_stats.get("scope", "ville")
    name = market_stats.get("scope_name") or "ce marché local"
    if scope == "quartier":
        base = f"Dans le quartier {name}"
    elif scope == "secteur":
        base = f"Dans le secteur {name} (quartiers voisins)"
    elif scope == "metropole":
        base = f"À l'échelle de {name} (communes voisines)"
    else:
        base = f"À l'échelle de {name}"
    if market_stats.get("dpe_band"):
        base += f" (DPE {market_stats['dpe_band']})"
    return base


def _scope_warning(market_stats: Dict[str, Any], property_city: str) -> str:
    """Avertissement (issue #87) quand le périmètre retenu est plus large que la
    commune du bien (à ce jour : repli métropole). Informe que la fourchette est
    un repère, pas une référence locale de la commune ; n'estime aucun prix."""
    if market_stats.get("scope") != "metropole":
        return ""
    scope_name = market_stats.get("scope_name") or _METRO_NAME
    return (
        f" Faute d'assez de transactions comparables à {property_city}, cette "
        f"fourchette reflète {scope_name} (communes voisines), pas "
        f"{property_city} seule : une commune recherchée peut s'en écarter "
        "durablement. À interpréter comme un repère, pas comme une référence "
        "locale."
    )


def interpret_price_positioning(
    listing_price_m2: float,
    market_stats: Dict[str, Any]
) -> Dict[str, str]:
    """
    Positionnement du prix selon la **distribution** observée (quartiles), pas
    un écart en % sur la médiane — robuste à la forte dispersion intra-marché.
    """
    q1 = market_stats["q1"]
    q3 = market_stats["q3"]
    iqr = max(q3 - q1, 0.0)
    upper_fence = q3 + 1.5 * iqr  # clôture haute de Tukey
    ctx = _scope_context(market_stats)

    def _r(v: float) -> int:
        return int(round(v))

    if listing_price_m2 <= q1:
        verdict = "Sous‑positionné"
        explanation = (
            f"{ctx}, le prix au m² est sous la fourchette courante observée "
            f"({_r(q1)}–{_r(q3)} €/m²) pour des biens comparables. À vérifier : "
            "état, étage, travaux ou particularité qui le justifierait."
        )
    elif listing_price_m2 <= q3:
        verdict = "Plutôt aligné"
        explanation = (
            f"{ctx}, le prix au m² se situe dans la fourchette courante observée "
            f"({_r(q1)}–{_r(q3)} €/m²) pour des biens comparables."
        )
    elif listing_price_m2 <= upper_fence:
        verdict = "Légèrement sur‑positionné"
        explanation = (
            f"{ctx}, le prix au m² dépasse la fourchette courante (au‑delà de "
            f"{_r(q3)} €/m²) mais reste dans les niveaux hauts déjà constatés."
        )
    else:
        verdict = "Fortement sur‑positionné"
        explanation = (
            f"{ctx}, le prix au m² dépasse nettement les niveaux observés "
            f"(au‑delà de {_r(upper_fence)} €/m²) pour des biens similaires."
        )

    return {"verdict": verdict, "explanation": explanation}


def _amenity_phrases(attrs: Optional[Dict[str, Any]]) -> List[str]:
    """Mentions factuelles des critères affinés du bien (chantier C), sans
    estimation : étage/ascenseur, terrasse, balcon, cave, parking."""
    if not attrs:
        return []
    phrases = []
    floor = attrs.get("floor")
    elevator = attrs.get("has_elevator")
    if attrs.get("property_type") == "maison":
        # Fix issue #80 : étage/ascenseur sont des notions d'appartement — bloc
        # entièrement neutralisé pour une maison explicite. « de plain-pied »
        # n'est rendu que sur preuve explicite (single_storey True) et jamais
        # si floor >= 1 (extraction contradictoire -> omission, prudence). Un
        # property_type null garde le comportement historique (conservateur).
        if attrs.get("single_storey") is True and not (
            isinstance(floor, int) and floor >= 1
        ):
            phrases.append("de plain-pied")
    elif isinstance(floor, int):
        loc = "rez-de-chaussée" if floor == 0 else f"{floor}er étage" if floor == 1 else f"{floor}e étage"
        if elevator is False and floor >= 2:
            loc += " sans ascenseur"
        phrases.append(loc)
    elif elevator is False:
        phrases.append("sans ascenseur")
    if attrs.get("has_terrace"):
        phrases.append("avec terrasse")
    if attrs.get("has_balcony"):
        phrases.append("avec balcon")
    if attrs.get("has_cellar"):
        phrases.append("avec cave")
    parking = attrs.get("parking")
    if isinstance(parking, int) and parking > 0:
        phrases.append(f"{parking} place{'s' if parking > 1 else ''} de parking")
    return phrases


def _criteria_signal(
    dpe: Optional[str],
    epoch: Optional[str],
    market_stats: Dict[str, Any],
    attrs: Optional[Dict[str, Any]] = None,
) -> str:
    """Signal explicatif (factuel, sans estimation de prix) : situe le DPE et
    l'époque du bien par rapport au profil des comparables, et rappelle ses
    critères affinés (étage, ascenseur, terrasse...). Couche 2 : enrichit
    l'explication, ne touche ni le verdict ni le score."""
    parts = []
    if dpe:
        pool_dpe = market_stats.get("pool_dpe")
        lr, pr = dpe_rank(dpe), dpe_rank(pool_dpe)
        if pool_dpe and lr is not None and pr is not None:
            if lr < pr:
                parts.append(f"DPE {dpe} (meilleur que le DPE médian {pool_dpe} des comparables)")
            elif lr > pr:
                parts.append(f"DPE {dpe} (moins bon que le DPE médian {pool_dpe} des comparables)")
            else:
                parts.append(f"DPE {dpe} (au niveau du DPE médian des comparables)")
        else:
            parts.append(f"DPE {dpe}")
    if epoch:
        parts.append({"neuf": "bien neuf", "récent": "construction récente",
                      "ancien": "construction ancienne"}.get(epoch, epoch))
    parts.extend(_amenity_phrases(attrs))
    if not parts:
        return ""
    return " À pondérer : " + ", ".join(parts) + "."


# ============================
# Indice de confiance
# ============================

def compute_confidence(market_stats: Dict[str, Any]) -> str:
    count = market_stats["count"]
    dispersion = market_stats["dispersion"]
    if count >= 10 and dispersion < 800:
        return "Élevée"
    elif count >= 4:
        return "Moyenne"
    else:
        return "Faible"


# ============================
# Fonction principale utilisée
# ============================

def compute_price_market_pillar(
    city: str,
    district: Optional[str],
    property_type: str,
    surface_m2: float,
    listing_price_m2: float,
    dpe: Optional[str] = None,
    construction_year: Optional[int] = None,
    attrs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pilier Prix / Marché appelé par analysis.py."""
    market_stats = compute_market_stats(
        city=city,
        district=district,
        property_type=property_type,
        surface_m2=surface_m2,
        dpe=dpe,
    )

    # Prix au m² de l'annonce, dérivé (prix total / surface) : repère factuel
    # exposé tel quel au front, y compris quand le marché local n'est pas
    # comparable — ce n'est pas une estimation, juste le chiffre de l'annonce.
    listing_price_m2_ref = int(round(listing_price_m2))

    if market_stats is None:
        return {
            "verdict": "Indéterminé",
            "explanation": (
                "Données comparables insuffisantes pour établir "
                "une référence fiable."
            ),
            "confidence": "Faible",
            "scope": None,
            "scope_name": None,
            "dpe_band": None,
            "n_comparables": 0,
            "refinable": False,
            "listing_price_m2": listing_price_m2_ref,
        }

    positioning = interpret_price_positioning(listing_price_m2, market_stats)
    epoch = construction_epoch(construction_year)
    explanation = (
        positioning["explanation"]
        + _criteria_signal(dpe, epoch, market_stats, attrs)
        + _scope_warning(market_stats, canonical_city(city))
    )

    return {
        "verdict": positioning["verdict"],
        "explanation": explanation,
        "confidence": compute_confidence(market_stats),
        # Périmètre exposé en clair pour un affichage structuré (badge) côté front.
        "scope": market_stats["scope"],
        "scope_name": market_stats["scope_name"],
        "dpe_band": market_stats["dpe_band"],
        "n_comparables": market_stats["count"],
        "listing_price_m2": listing_price_m2_ref,
        # Analyse restée large (ville ou métropole) pour un bien messin : on peut
        # l'affiner si l'utilisateur précise le quartier (sélecteur Metz côté
        # front). Inutile hors Metz : le sélecteur ne propose que des quartiers
        # de Metz.
        "refinable": (
            market_stats["scope"] in ("ville", "metropole")
            and canonical_city(city) == canonical_city("Metz")
        ),
    }
