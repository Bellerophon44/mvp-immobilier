import logging
from typing import Any, Dict

from app.llm_semantic import analyze_semantic
from app.market_stats import compute_price_market_pillar
from app.scoring import compute_global_score
from scrapers.base import extract_district


logger = logging.getLogger("analysis")


def _price_pillar_from_listing(
    listing: Dict[str, Any], raw_text: str = "", district_override: str = ""
) -> Dict[str, Any]:
    """Construit le pilier prix/marché à partir des données extraites par le LLM.

    `district_override` (choisi par l'utilisateur via le sélecteur de quartier)
    prime sur l'extraction quand il est fourni, pour affiner une analyse restée
    au niveau ville. Renvoie un pilier "Indéterminé" si l'extraction est
    insuffisante.
    """
    city = listing.get("city")
    surface = listing.get("surface_m2")
    price_total = listing.get("price_total")
    property_type = listing.get("property_type") or "appartement"

    if not city or not surface or not price_total or surface <= 0:
        return {
            "verdict": "Indéterminé",
            "explanation": (
                "Informations chiffrées insuffisantes dans l'annonce "
                "pour comparer au marché local."
            ),
            "confidence": "Faible",
        }

    listing_price_m2 = price_total / surface

    # Quartier : choix explicite de l'utilisateur en priorité absolue ; sinon
    # extraction LLM ; sinon repli sur les localités connues du Grand Metz
    # détectées dans le texte (augmente le taux de comparaison au niveau quartier).
    district = district_override or listing.get("district") or extract_district(raw_text)

    return compute_price_market_pillar(
        city=city,
        district=district,
        property_type=property_type,
        surface_m2=surface,
        listing_price_m2=listing_price_m2,
        dpe=listing.get("dpe"),
        construction_year=listing.get("construction_year"),
    )


def run_full_analysis(raw_text: str, district_override: str = "") -> dict:
    semantic_result = analyze_semantic(raw_text)
    listing = semantic_result.get("listing") or {}
    logger.info("LLM extracted listing: %s", listing)
    price_market_pillar = _price_pillar_from_listing(
        listing, raw_text, district_override
    )

    pillars = [
        {
            "label": "Prix vs marché local",
            "verdict": price_market_pillar["verdict"],
            "explanation": price_market_pillar["explanation"],
            # Périmètre structuré pour l'affichage (badge dynamique côté front).
            "scope": price_market_pillar.get("scope"),
            "scope_name": price_market_pillar.get("scope_name"),
            "dpe_band": price_market_pillar.get("dpe_band"),
            "n_comparables": price_market_pillar.get("n_comparables"),
            "refinable": price_market_pillar.get("refinable", False),
        },
        {
            "label": "Transparence de l'annonce",
            "verdict": semantic_result["verdict"],
            "explanation": semantic_result["summary"],
        },
        {
            "label": "Risques et incertitudes",
            "verdict": semantic_result["risk_level"],
            "explanation": semantic_result["risk_summary"],
        },
    ]

    score_block = compute_global_score(
        price_pillar=price_market_pillar,
        semantic_pillar=semantic_result,
    )

    actions = {
        "check": semantic_result["to_check"],
        "questions": semantic_result["questions"],
        "negotiation": semantic_result["negotiation_levers"],
    }

    return {
        "global_score": score_block["score"],
        "verdict": score_block["verdict"],
        "confidence": score_block["confidence"],
        "pillars": pillars,
        "actions": actions,
    }
