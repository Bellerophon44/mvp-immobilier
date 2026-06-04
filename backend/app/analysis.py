import logging
from typing import Any, Dict

from app.llm_semantic import analyze_semantic
from app.market_stats import compute_price_market_pillar
from app.metz_local import assess_claims, local_context
from app.scoring import compute_global_score
from scrapers.base import extract_district


logger = logging.getLogger("analysis")


def _price_pillar_from_listing(
    listing: Dict[str, Any], raw_text: str = "", district_override: str = "",
    address: str = "",
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

    district = _resolve_district(listing, raw_text, district_override, address)

    return compute_price_market_pillar(
        city=city,
        district=district,
        property_type=property_type,
        surface_m2=surface,
        listing_price_m2=listing_price_m2,
        dpe=listing.get("dpe"),
        construction_year=listing.get("construction_year"),
        attrs=_amenity_attrs(listing),
    )


_AMENITY_KEYS = (
    "floor", "has_elevator", "has_terrace", "has_balcony",
    "has_cellar", "parking", "bedrooms", "condo_fees",
)


def _amenity_attrs(listing: Dict[str, Any]) -> Dict[str, Any]:
    return {k: listing.get(k) for k in _AMENITY_KEYS}


def _resolve_district(
    listing: Dict[str, Any], raw_text: str, district_override: str, address: str = ""
) -> str:
    """Quartier retenu pour l'analyse, par ordre de fiabilité décroissante :
    choix explicite de l'utilisateur (sélecteur quartier) ; quartier déduit de
    l'adresse saisie par l'utilisateur (alternative manuelle au géocodage) ;
    extraction LLM ; repli sur les localités du Grand Metz détectées dans le texte.
    """
    return (
        district_override
        or (extract_district(address) if address else None)
        or listing.get("district")
        or extract_district(raw_text)
        or ""
    )


def _amenity_actions(listing: Dict[str, Any]) -> Dict[str, list]:
    """Questions / leviers déterministes tirés des critères affinés. Factuels,
    jamais estimatifs : on interroge ou on signale, on n'évalue pas. Les items
    sont formulés en questions pour rejoindre la liste unique `questions`."""
    questions, negotiation = [], []
    floor = listing.get("floor")
    if isinstance(floor, int) and floor >= 3 and listing.get("has_elevator") is False:
        questions.append(
            f"Le bien est au {floor}e étage sans ascenseur : comment se passe l'accès "
            "au quotidien (déménagement, accessibilité) et est-ce un frein à la revente ?"
        )
        negotiation.append(f"{floor}e étage sans ascenseur")
    fees = listing.get("condo_fees")
    if fees:
        questions.append(
            f"Que couvrent les charges de copropriété annoncées ({int(fees)} €/an) "
            "et ont-elles évolué récemment ?"
        )
    return {"questions": questions, "negotiation": negotiation}


def _merge_unique(base: list, extra: list) -> list:
    """Concatène en évitant les doublons (insensible à la casse/espaces)."""
    seen = {str(x).strip().lower() for x in base}
    return list(base) + [x for x in extra if str(x).strip().lower() not in seen]


def run_full_analysis(
    raw_text: str, district_override: str = "", address: str = ""
) -> dict:
    semantic_result = analyze_semantic(raw_text)
    listing = semantic_result.get("listing") or {}
    logger.info("LLM extracted listing: %s", listing)
    price_market_pillar = _price_pillar_from_listing(
        listing, raw_text, district_override, address
    )

    # Contexte local non-scoré (couche A "Ancrage local") : profil curaté du
    # quartier retenu, ou None s'il n'est pas reconnu (on n'affiche rien plutôt
    # que d'inventer). L'adresse saisie (alternative manuelle au géocodage) aide
    # à fixer le quartier.
    city = listing.get("city") or "Metz"
    district = _resolve_district(listing, raw_text, district_override, address)
    local_ctx = local_context(district, city)
    if local_ctx is not None:
        # Couche B : confronte les allégations locales de l'annonce au profil.
        local_ctx["claims"] = assess_claims(
            district, semantic_result.get("local_claims") or [], city
        )
        if address and address.strip():
            local_ctx["address"] = address.strip()

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

    extra = _amenity_actions(listing)
    actions = {
        "questions": _merge_unique(semantic_result["questions"], extra["questions"]),
        "negotiation": _merge_unique(semantic_result["negotiation_levers"], extra["negotiation"]),
    }

    return {
        "global_score": score_block["score"],
        "verdict": score_block["verdict"],
        "confidence": score_block["confidence"],
        "pillars": pillars,
        "actions": actions,
        "local_context": local_ctx,
    }
