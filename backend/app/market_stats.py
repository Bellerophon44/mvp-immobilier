import logging

import numpy as np
from typing import Optional, Dict, Any

from db.session import SessionLocal
from db.models import Comparable
from scrapers.base import canonical_city


logger = logging.getLogger("market_stats")


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
    surface_max: float
):
    """
    Récupère les annonces comparables depuis la DB
    selon des critères simples et explicables.
    """
    db = SessionLocal()

    query = db.query(Comparable).filter(
        Comparable.city == city,
        Comparable.property_type == property_type,
        Comparable.surface_m2 >= surface_min,
        Comparable.surface_m2 <= surface_max
    )

    if district:
        query = query.filter(Comparable.district == district)

    results = query.all()
    db.close()

    return results


# ============================
# Calcul des statistiques marché
# ============================

def compute_market_stats(
    city: str,
    district: Optional[str],
    property_type: str,
    surface_m2: float
) -> Optional[Dict[str, Any]]:
    """
    Calcule les statistiques du marché local observable.

    Retourne None si données insuffisantes.
    """

    # Même normalisation que les scrapers : la ville extraite de l'annonce doit
    # matcher la clé canonique sous laquelle les comparables sont stockés.
    city = canonical_city(city)

    # Fourchette MVP : ±20 % autour de la surface
    surface_min = surface_m2 * 0.8
    surface_max = surface_m2 * 1.2

    # 1er essai : avec district si fourni (résultat plus précis)
    comparables = _fetch_comparables(
        city=city,
        district=district,
        property_type=property_type,
        surface_min=surface_min,
        surface_max=surface_max,
    )
    logger.info(
        "market_stats query: city=%r district=%r type=%r surface=[%.0f-%.0f] -> %d comparables",
        city, district, property_type, surface_min, surface_max, len(comparables),
    )

    # 2e essai : si trop peu de matchs avec district, on retombe ville+type
    # (les libellés de district varient entre sources, pas fiable comme filtre dur)
    if district and len(comparables) < 3:
        comparables = _fetch_comparables(
            city=city,
            district=None,
            property_type=property_type,
            surface_min=surface_min,
            surface_max=surface_max,
        )
        logger.info(
            "market_stats fallback (no district): %d comparables",
            len(comparables),
        )

    if len(comparables) < 3:
        return None

    prices_m2 = [c.price_m2 for c in comparables]

    q1 = _percentile(prices_m2, 25)
    median = _median(prices_m2)
    q3 = _percentile(prices_m2, 75)

    dispersion = q3 - q1

    return {
        "count": len(prices_m2),
        "median": median,
        "q1": q1,
        "q3": q3,
        "dispersion": dispersion
    }


# ============================
# Interprétation métier (pilier)
# ============================

def interpret_price_positioning(
    listing_price_m2: float,
    market_stats: Dict[str, Any]
) -> Dict[str, str]:
    """
    Interprète le positionnement du prix par rapport à la **distribution**
    observée (quartiles), et non à un simple écart en % sur la médiane. Le
    marché local est souvent très dispersé (ex. Metz : Borny ~900 €/m² vs
    centre ~3000) : comparer à la fourchette interquartile évite de juger
    "fortement sur‑positionné" un bien qui reste dans les niveaux constatés.
    """

    q1 = market_stats["q1"]
    q3 = market_stats["q3"]
    iqr = max(q3 - q1, 0.0)
    upper_fence = q3 + 1.5 * iqr  # clôture haute de Tukey

    def _r(v: float) -> int:
        return int(round(v))

    if listing_price_m2 <= q1:
        verdict = "Sous‑positionné"
        explanation = (
            f"Le prix au m² est sous la fourchette courante observée "
            f"({_r(q1)}–{_r(q3)} €/m²) pour des biens comparables. À vérifier : "
            "état, étage, travaux ou particularité qui le justifierait."
        )
    elif listing_price_m2 <= q3:
        verdict = "Plutôt aligné"
        explanation = (
            f"Le prix au m² se situe dans la fourchette courante observée "
            f"({_r(q1)}–{_r(q3)} €/m²) pour des biens comparables sur ce "
            "marché local."
        )
    elif listing_price_m2 <= upper_fence:
        verdict = "Légèrement sur‑positionné"
        explanation = (
            f"Le prix au m² dépasse la fourchette courante (au‑delà de "
            f"{_r(q3)} €/m²) mais reste dans les niveaux hauts déjà constatés "
            "localement."
        )
    else:
        verdict = "Fortement sur‑positionné"
        explanation = (
            f"Le prix au m² dépasse nettement les niveaux observés "
            f"(au‑delà de {_r(upper_fence)} €/m²) pour des biens similaires."
        )

    return {
        "verdict": verdict,
        "explanation": explanation
    }


# ============================
# Indice de confiance
# ============================

def compute_confidence(market_stats: Dict[str, Any]) -> str:
    """
    Détermine un niveau de confiance explicite
    selon la quantité et la dispersion des données.
    """

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
    listing_price_m2: float
) -> Dict[str, Any]:
    """
    Fonction appelée par analysis.py
    pour construire le pilier Prix / Marché.
    """

    market_stats = compute_market_stats(
        city=city,
        district=district,
        property_type=property_type,
        surface_m2=surface_m2
    )

    if market_stats is None:
        return {
            "verdict": "Indéterminé",
            "explanation": (
                "Données comparables insuffisantes pour établir "
                "une référence fiable."
            ),
            "confidence": "Faible"
        }

    positioning = interpret_price_positioning(
        listing_price_m2=listing_price_m2,
        market_stats=market_stats
    )

    confidence = compute_confidence(market_stats)

    return {
        "verdict": positioning["verdict"],
        "explanation": positioning["explanation"],
        "confidence": confidence
    }

# ============================
