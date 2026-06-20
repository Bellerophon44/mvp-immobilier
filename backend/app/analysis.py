import logging
from typing import Any, Dict, Optional

from app.llm_semantic import analyze_semantic
from app.market_stats import compute_price_market_pillar
from app.photo_evidence import assess_claims_with_photos
from app.geocode import geocode_address
import app.metz_local as metz_local
from app.metz_local import (
    _resolve_key,
    assess_claims,
    claim_distances_from_coords,
    local_context,
    local_context_from_coords,
)
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


# property_type / single_storey ne sont pas des "amenities" mais le rendu en a
# besoin (fix issue #80) : étage/ascenseur sont des notions d'appartement, et
# « de plain-pied » exige la preuve explicite single_storey.
_AMENITY_KEYS = (
    "floor", "has_elevator", "has_terrace", "has_balcony",
    "has_cellar", "parking", "bedrooms", "condo_fees",
    "property_type", "single_storey",
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
    # Fix issue #80 : étage/ascenseur sont des notions d'appartement — jamais
    # de question ni de levier étage-ascenseur pour une maison explicite
    # (même invariant que le rendu _amenity_phrases). Un property_type null
    # garde le comportement actuel (conservateur).
    is_house = listing.get("property_type") == "maison"
    if (
        not is_house
        and isinstance(floor, int) and floor >= 3
        and listing.get("has_elevator") is False
    ):
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


def _derived_negotiation_levers(
    price_pillar: Dict[str, Any],
    listing: Dict[str, Any],
    local_ctx: Optional[Dict[str, Any]],
) -> list:
    """Leviers de négociation déterministes tirés de l'analyse elle-même (pas du
    LLM), côté acheteur : positionnement prix défavorable au vendeur, DPE faible,
    allégation locale peu plausible. Factuels, jamais estimatifs (aucun prix
    cible). Ordre stable : prix d'abord (levier principal), puis DPE, puis
    allégations."""
    levers: list = []

    verdict = (price_pillar.get("verdict") or "").lower()
    # Verdicts "sur-positionné" (le tiret est un U+2011 insécable) : le prix
    # dépasse la fourchette locale observée -> levier principal. "sous-positionné"
    # ne contient pas "sur" et est donc exclu (favorable à l'acheteur).
    if "sur" in verdict and "position" in verdict:
        if "fort" in verdict:
            levers.append(
                "Prix au m² nettement au-dessus des niveaux observés localement "
                "pour des biens comparables — principal levier à la baisse."
            )
        else:
            levers.append(
                "Prix au m² au-dessus de la fourchette habituelle du marché "
                "local observé pour des biens comparables."
            )

    dpe = (listing.get("dpe") or "").upper()
    if dpe in ("F", "G"):
        levers.append(
            f"DPE {dpe} (passoire thermique) : travaux d'amélioration énergétique "
            "à prévoir, à intégrer à la négociation."
        )

    for claim in (local_ctx or {}).get("claims") or []:
        if claim.get("status") == "peu_plausible":
            text = (claim.get("text") or "").strip()
            if text:
                levers.append(
                    f"Allégation « {text} » peu plausible localement — "
                    "à faire préciser et relativiser dans la discussion."
                )

    return levers


def _merge_unique(base: list, extra: list) -> list:
    """Concatène en évitant les doublons (insensible à la casse/espaces)."""
    seen = {str(x).strip().lower() for x in base}
    return list(base) + [x for x in extra if str(x).strip().lower() not in seen]


def _merge_photo_status(local_ctx, image_urls) -> None:
    """Fusionne `photo_status` dans chaque claim eligible de local_ctx['claims']
    (mode URL uniquement). Les claims non eligibles restent inchanges (pas de cle).
    Aucun effet de bord si pas de contexte local ou pas de claims."""
    if not image_urls or local_ctx is None:
        return
    ctx_claims = local_ctx.get("claims") or []
    if not ctx_claims:
        return
    mapping = assess_claims_with_photos(ctx_claims, image_urls)
    for idx, status in mapping.items():
        if 0 <= idx < len(ctx_claims):
            ctx_claims[idx]["photo_status"] = status


def _record_llm_fallback_event() -> None:
    """Persiste l'event serveur `llm_fallback` au point unique du fallback LLM.

    Best-effort : une erreur DB ne doit jamais faire echouer /analyze (le
    marqueur interne n'est de toute facon pas expose dans la reponse).
    """
    from db.models import Event
    from db.session import SessionLocal

    db = None
    try:
        db = SessionLocal()
        db.add(Event(name="llm_fallback", reason="llm_fallback"))
        db.commit()
    except Exception:
        logger.exception("failed to record llm_fallback event")
    finally:
        if db is not None:
            db.close()


def run_full_analysis(
    raw_text: str, district_override: str = "", address: str = "",
    image_urls=None,
) -> dict:
    semantic_result = analyze_semantic(raw_text)
    if semantic_result.get("_fallback"):
        _record_llm_fallback_event()
    listing = semantic_result.get("listing") or {}
    logger.info("LLM extracted listing: %s", listing)
    price_market_pillar = _price_pillar_from_listing(
        listing, raw_text, district_override, address
    )

    # Contexte local non-scoré ("Ancrage local"). L'adresse saisie est d'abord
    # géocodée (couche C) pour des distances exactes ; à défaut (adresse absente,
    # non géocodable, hors périmètre, réseau indisponible) on retombe sur le
    # profil curaté du quartier (couches A/B).
    city = listing.get("city") or "Metz"
    district = _resolve_district(listing, raw_text, district_override, address)
    claims = semantic_result.get("local_claims") or []
    addr = (address or "").strip()

    geo = geocode_address(addr, city) if addr else None
    if geo is not None:
        local_ctx = local_context_from_coords(
            geo["lat"], geo["lon"], district, city, address=geo.get("label") or addr
        )
        # Ecole mesuree la plus proche (tous degres) pour enrichir la note du
        # claim `ecoles` (volet D.3). Best-effort : un echec n'empeche pas
        # l'evaluation des autres claims.
        nearest_school = None
        try:
            schools = metz_local.nearest_schools(geo["lat"], geo["lon"])
            if schools:
                nearest_school = min(schools, key=lambda s: s.get("distance_km", float("inf")))
        except Exception:
            logger.exception("nearest_schools indisponible pour la note ecoles")
        local_ctx["claims"] = assess_claims(
            district, claims, city,
            dist_override=claim_distances_from_coords(geo["lat"], geo["lon"]),
            nearest_school=nearest_school,
        )
    else:
        # Garde-fou C2 (branche sans géocodage uniquement) : si le quartier
        # retenu vient d'un override utilisateur que l'annonce ne corrobore PAS
        # (clé d'extraction différente ou absente), on pose une réserve et on
        # rétrograde les claims sinon cohérents. Règle binaire déterministe
        # (override vs extraction), pas de détection géographique réelle.
        corroborated: Optional[bool] = None
        if district_override:
            k_override = _resolve_key(district_override, city)
            k_extracted = _resolve_key(
                listing.get("district") or extract_district(raw_text), city
            )
            corroborated = (
                k_extracted is not None and k_override == k_extracted
            )
        local_ctx = local_context(district, city, district_corroborated=corroborated)
        if local_ctx is not None:
            local_ctx["claims"] = assess_claims(
                district, claims, city, district_corroborated=corroborated
            )
            if addr:
                local_ctx["address"] = addr

    _merge_photo_status(local_ctx, image_urls)

    score_block = compute_global_score(
        price_pillar=price_market_pillar,
        semantic_pillar=semantic_result,
    )
    breakdown = score_block["breakdown"]

    # `points`/`max` exposent la part de chaque pilier dans le score global, pour
    # que le front affiche les mêmes nombres (global = prix + transparence +
    # risque) au lieu de recalculer des barres divergentes.
    pillars = [
        {
            "label": "Prix vs marché local",
            "verdict": price_market_pillar["verdict"],
            "explanation": price_market_pillar["explanation"],
            "points": breakdown["price"],
            "max": 40,
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
            "points": breakdown["transparency"],
            "max": 30,
        },
        {
            "label": "Risques et incertitudes",
            "verdict": semantic_result["risk_level"],
            "explanation": semantic_result["risk_summary"],
            "points": breakdown["risk"],
            "max": 30,
        },
    ]

    extra = _amenity_actions(listing)
    # Leviers = leviers LLM (recentrés côté acheteur) + leviers déterministes
    # confort (étage/ascenseur) + leviers dérivés de l'analyse (prix, DPE,
    # allégations). `highlights` = atouts factuels du bien (LLM uniquement),
    # section distincte pour objectiver la valeur avant la négociation.
    derived = _derived_negotiation_levers(price_market_pillar, listing, local_ctx)
    negotiation = _merge_unique(semantic_result["negotiation_levers"], extra["negotiation"])
    actions = {
        "highlights": list(semantic_result.get("highlights") or []),
        "questions": _merge_unique(semantic_result["questions"], extra["questions"]),
        "negotiation": _merge_unique(negotiation, derived),
    }

    return {
        "global_score": score_block["score"],
        "verdict": score_block["verdict"],
        "confidence": score_block["confidence"],
        "pillars": pillars,
        "actions": actions,
        "local_context": local_ctx,
    }
