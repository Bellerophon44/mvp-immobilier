import numpy as np
from typing import Optional, Dict, Any

from db.session import SessionLocal
from db.models import Comparable


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

    # Fourchette MVP : ±20 % autour de la surface
    surface_min = surface_m2 * 0.8
    surface_max = surface_m2 * 1.2

    comparables = _fetch_comparables(
        city=city,
        district=district,
        property_type=property_type,
        surface_min=surface_min,
        surface_max=surface_max
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
    Interprète le positionnement du prix
    par rapport au marché observable.
    """

    median = market_stats["median"]
    gap = (listing_price_m2 - median) / median

    # Seuils MVP explicables
    aligned_threshold = 0.10        # ±10 %
    warning_threshold = 0.25        # +25 %

    if abs(gap) <= aligned_threshold:
        verdict = "Plutôt aligné"
        explanation = (
            "Le prix se situe dans la fourchette observée "
            "pour des biens comparables sur ce marché local."
        )
    elif gap > aligned_threshold and gap <= warning_threshold:
        verdict = "Légèrement sur‑positionné"
        explanation = (
            "Le prix est supérieur à la tendance observée, "
            "mais reste dans une zone couramment constatée."
        )
    elif gap > warning_threshold:
        verdict = "Fortement sur‑positionné"
        explanation = (
            "Le prix est nettement au‑dessus des niveaux observés "
            "pour des biens similaires."
        )
    else:
        verdict = "Sous‑positionné"
        explanation = (
            "Le prix est inférieur aux tendances observées sur ce marché local."
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
