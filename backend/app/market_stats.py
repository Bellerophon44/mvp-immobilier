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


logger = logging.getLogger("market_stats")


# Un filtre plus précis (quartier, bande DPE) n'est retenu que si son
# sous-échantillon reste assez fourni, sinon ses quartiles sont trompeurs : on
# retombe sur un périmètre plus large et plus robuste. Même seuil que la
# confiance "Élevée".
MIN_REFINED_COMPARABLES = 10
MIN_COMPARABLES = 3  # plancher absolu (niveau ville)
MIN_PROFILE = 5      # mini pour calculer un profil DPE/année de pool fiable


# Secteurs de Metz : regroupements de quartiers adjacents. Quand un quartier est
# trop creux pour des quartiles fiables, on emprunte aux quartiers voisins du
# même secteur AVANT de retomber sur toute la ville — toujours 100% comparables
# observés, jamais d'estimation. Les libellés bruts ci-dessous sont normalisés
# via canonical_district au chargement pour matcher les valeurs stockées (y
# compris les formes composées de bien'ici, ex. 'Plantières - Queuleu').
_SECTORS_RAW = {
    # Découpage validé manuellement. Plusieurs secteurs ne contiennent qu'un seul
    # quartier (volume déjà suffisant) : la cascade n'y gagne rien mais le secteur
    # documente l'intention. Les regroupements utiles : Bellecroix+Vallières et
    # les 4 quartiers du centre. Les formes mono (sélecteur front) sont rattachées
    # à leur quartier réel pour que le choix utilisateur tombe sur le bon pool.
    "Devant-les-Ponts": ["Devant-les-Ponts"],
    "Patrotte-Metz-Nord": ["Patrotte-Metz-Nord", "La Patrotte"],
    "Sablon": ["Sablon"],
    "Plantières-Queuleu": ["Plantières - Queuleu", "Queuleu", "Plantières"],
    "Magny": ["Magny"],
    "Borny": ["Borny"],
    "Bellecroix - Vallières": ["Bellecroix", "Vallières-lès-Bordes", "Vallières"],
    "Centre Ville": ["Centre-Ville", "Ancienne-Ville", "Nouvelle Ville", "Les Îles", "Outre-Seille"],
}


def _build_sector_maps():
    """Construit, à partir de _SECTORS_RAW, le mapping quartier_canonique ->
    secteur et secteur -> liste de quartiers canoniques (pour le filtre SQL)."""
    district_to_sector: Dict[str, str] = {}
    sector_districts: Dict[str, List[str]] = {}
    for sector, quartiers in _SECTORS_RAW.items():
        canon = []
        for q in quartiers:
            cq = canonical_district(q, "Metz")
            if cq and cq not in canon:
                canon.append(cq)
                district_to_sector[cq] = sector
        sector_districts[sector] = canon
    return district_to_sector, sector_districts


_DISTRICT_TO_SECTOR, _SECTOR_DISTRICTS = _build_sector_maps()


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
):
    """Récupère les comparables selon des critères simples et explicables.

    `districts` (liste) filtre sur un ensemble de quartiers — utilisé pour le
    périmètre secteur ; `district` (str) filtre sur un seul quartier."""
    db = SessionLocal()
    try:
        query = db.query(Comparable).filter(
            Comparable.city == city,
            Comparable.property_type == property_type,
            Comparable.surface_m2 >= surface_min,
            Comparable.surface_m2 <= surface_max,
        )
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
      quartier+DPE -> quartier -> secteur+DPE -> secteur -> ville+DPE -> ville.
    Le secteur (quartiers voisins) comble les quartiers creux sans diluer
    jusqu'à toute la ville. Retourne None si même la ville est trop pauvre.
    """
    city = canonical_city(city)
    district = canonical_district(district, city)
    band = dpe_band(dpe)
    band_letters = DPE_BANDS.get(band) if band else None

    sector = _DISTRICT_TO_SECTOR.get(district) if district else None
    sector_districts = _SECTOR_DISTRICTS.get(sector) if sector else None

    surface_min = surface_m2 * 0.8
    surface_max = surface_m2 * 1.2

    # Niveaux candidats, du plus précis au plus large.
    # Chaque candidat : (scope, scope_name, district, districts, band).
    candidates = []
    if district and band_letters:
        candidates.append(("quartier", district, district, None, band))
    if district:
        candidates.append(("quartier", district, district, None, None))
    if sector_districts and band_letters:
        candidates.append(("secteur", sector, None, sector_districts, band))
    if sector_districts:
        candidates.append(("secteur", sector, None, sector_districts, None))
    if band_letters:
        candidates.append(("ville", city, None, None, band))
    candidates.append(("ville", city, None, None, None))  # base

    chosen = None
    for scope, name, dist, dists, b in candidates:
        comparables = _fetch_comparables(
            city, dist, property_type, surface_min, surface_max,
            DPE_BANDS.get(b) if b else None, districts=dists,
        )
        is_base = (scope == "ville" and b is None)
        if is_base or len(comparables) >= MIN_REFINED_COMPARABLES:
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
    else:
        base = f"À l'échelle de {name}"
    if market_stats.get("dpe_band"):
        base += f" (DPE {market_stats['dpe_band']})"
    return base


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
    if isinstance(floor, int):
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
        }

    positioning = interpret_price_positioning(listing_price_m2, market_stats)
    epoch = construction_epoch(construction_year)
    explanation = positioning["explanation"] + _criteria_signal(dpe, epoch, market_stats, attrs)

    return {
        "verdict": positioning["verdict"],
        "explanation": explanation,
        "confidence": compute_confidence(market_stats),
        # Périmètre exposé en clair pour un affichage structuré (badge) côté front.
        "scope": market_stats["scope"],
        "scope_name": market_stats["scope_name"],
        "dpe_band": market_stats["dpe_band"],
        "n_comparables": market_stats["count"],
        # Au niveau ville : l'analyse pourrait être affinée si l'utilisateur
        # précisait le quartier (déclenche le sélecteur côté front).
        "refinable": market_stats["scope"] == "ville",
    }
