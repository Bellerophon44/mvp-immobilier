import json
import logging
from typing import Optional

from scrapers.base import (
    fetch_json,
    generate_stable_id,
    canonical_city,
    canonical_district,
    normalize_postal_code,
    _session,
    REQUEST_TIMEOUT,
)
from scrapers.models import PropertyListing
from scrapers.registry import register

logger = logging.getLogger(__name__)

SOURCE_NAME = "bienici"
ADS_URL = "https://www.bienici.com/realEstateAds.json"
SUGGEST_URLS = [
    "https://res.bienici.com/suggest.json",
    "https://www.bienici.com/suggest.json",
]

PAGE_SIZE = 50
# L'API plafonne la pagination à ~2500 résultats (offset 2500), alors que le
# total dépasse 27000 et que le tri par défaut sert les PETITES surfaces d'abord.
# Paginer plus loin ne suffit donc pas : on balaie par tranches de surface
# (minArea/maxArea), chaque tranche faisant moins que le plafond, ce qui couvre
# toutes les tailles. Plafond de pages par tranche, par sécurité.
MAX_PAGES = 50

# Tranches de surface (m²) balayées séparément. Fines sur le bas (dense) pour ne
# pas heurter le plafond de pagination, plus larges sur le haut (rare). None = borne
# ouverte. Couvre tout le spectre, studios comme grandes maisons.
SURFACE_BUCKETS = [
    (0, 25), (25, 35), (35, 45), (45, 55), (55, 65),
    (65, 80), (80, 100), (100, 130), (130, None),
]

_VALID_DPE = {"A", "B", "C", "D", "E", "F", "G"}

# Bande de plausibilité du prix au m² pour une VENTE résidentielle.
# Sert de filet contre les loyers, viagers, parkings et erreurs de saisie
# qui polluent les comparables (le marché messin tourne ~1500-4000 €/m²).
MIN_PRICE_M2 = 800.0
MAX_PRICE_M2 = 12000.0

_PROPERTY_TYPE_MAP = {
    "flat": "appartement",
    "studio": "appartement",
    "loft": "appartement",
    "duplex": "appartement",
    "house": "maison",
    "villa": "maison",
    "castle": "maison",
    "townhouse": "maison",
    "manor": "maison",
}


def discover_zone_ids(city_name: str) -> list:
    """
    Récupère les zoneIds internes Bien'ici pour une ville via l'endpoint
    de suggestion. Ex: 'Metz' -> ['-450381'].

    Retourne [] si rien trouvé.
    """
    for url in SUGGEST_URLS:
        try:
            r = _session.get(url, params={"q": city_name}, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            suggestions = r.json()
        except Exception as e:
            logger.warning("Bienici suggest failed (%s): %s", url, e)
            continue

        if not isinstance(suggestions, list):
            continue

        # 1) match exact sur une ville
        for s in suggestions:
            if (s.get("type") == "city"
                    and str(s.get("name", "")).lower() == city_name.lower()
                    and s.get("zoneIds")):
                logger.info("Bienici: zoneIds %s pour '%s'",
                            s["zoneIds"], city_name)
                return s["zoneIds"]

        # 2) fallback : première suggestion de type ville avec zoneIds
        for s in suggestions:
            if s.get("type") == "city" and s.get("zoneIds"):
                logger.info("Bienici: zoneIds (fallback) %s pour '%s'",
                            s["zoneIds"], city_name)
                return s["zoneIds"]

    logger.warning("Bienici: aucun zoneId trouvé pour '%s'", city_name)
    return []


def _build_filters(zone_ids: list, page: int,
                   min_area: Optional[float] = None,
                   max_area: Optional[float] = None) -> dict:
    filters = {
        "size": PAGE_SIZE,
        "from": page * PAGE_SIZE,
        "filterType": "buy",
        "propertyType": list(_PROPERTY_TYPE_MAP.keys()),
        "zoneIdsByTypes": {"zoneIds": zone_ids},
    }
    if min_area is not None:
        filters["minArea"] = min_area
    if max_area is not None:
        filters["maxArea"] = max_area
    return {"filters": json.dumps(filters)}


def _scalar(value) -> Optional[float]:
    """
    Retourne un float si la valeur est un nombre simple.
    Retourne None si c'est une liste (programme neuf = fourchette de
    prix/surface) ou tout autre type non exploitable.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _extract_postal(ad: dict) -> Optional[str]:
    """Code postal d'une annonce bien'ici. Le nom exact du champ est confirmé par
    l'audit (scrapers.diag_bienici.field_audit_md) ; on teste les candidats
    plausibles pour rester robuste, et on retombe sur le bloc district."""
    for key in ("postalCode", "cityZipCode", "zipCode"):
        pc = normalize_postal_code(ad.get(key))
        if pc:
            return pc
    district = ad.get("district")
    if isinstance(district, dict):
        return normalize_postal_code(district.get("postalCode"))
    return None


def _as_bool(value) -> Optional[bool]:
    return value if isinstance(value, bool) else None


def _as_int(value) -> Optional[int]:
    if isinstance(value, bool):
        return None
    return int(value) if isinstance(value, (int, float)) and value >= 0 else None


def _as_float(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, (int, float)) and value >= 0 else None


def _has_feature(ad: dict, flag_key: str, qty_key: str) -> Optional[bool]:
    """Présence d'un équipement : flag booléen direct, sinon déduit d'un compteur
    (>0), sinon None si l'API n'expose ni l'un ni l'autre."""
    flag = ad.get(flag_key)
    if isinstance(flag, bool):
        return flag
    qty = ad.get(qty_key)
    if isinstance(qty, (int, float)) and not isinstance(qty, bool):
        return qty > 0
    return None


def _extract_amenities(ad: dict) -> dict:
    """Critères affinés (chantier C) exposés par l'API bien'ici. Noms de champs
    confirmés par l'audit (field_audit_md). Tous nullables : absent -> None."""
    return {
        "floor": _as_int(ad.get("floor")),
        "has_elevator": _as_bool(ad.get("hasElevator")),
        "has_terrace": _has_feature(ad, "hasTerrace", "terracesQuantity"),
        "has_balcony": _has_feature(ad, "hasBalcony", "balconyQuantity"),
        "is_condo": _as_bool(ad.get("isInCondominium")),
        "condo_fees": _as_float(ad.get("annualCondominiumFees")),
        "has_cellar": _has_feature(ad, "hasCellar", "cellarsOrUndergroundsQuantity"),
        "parking": _as_int(ad.get("parkingPlacesQuantity")),
        "bedrooms": _as_int(ad.get("bedroomsQuantity")),
    }


def _parse_listing(ad: dict) -> Optional[PropertyListing]:
    # On ne garde que les ventes classiques. L'API renvoie 'buy' pour une
    # vente standard et 'lifeAnnuitySale' pour un viager — qu'on rejette
    # car son prix bouquet n'est pas comparable à un prix de marché.
    if ad.get("adType") != "buy":
        return None

    price = _scalar(ad.get("price"))
    surface = _scalar(ad.get("surfaceArea"))
    if not price or not surface or price <= 0 or surface <= 0:
        return None

    property_type = _PROPERTY_TYPE_MAP.get(ad.get("propertyType", ""))
    if property_type is None:
        return None  # bureau, terrain, parking, local... → ignoré

    # Filet de plausibilité : éjecte loyers, viagers, parkings, erreurs.
    price_m2 = price / surface
    if price_m2 < MIN_PRICE_M2 or price_m2 > MAX_PRICE_M2:
        return None

    district = ad.get("district")
    district_name = district.get("name") if isinstance(district, dict) else None

    postal_code = _extract_postal(ad)

    dpe = ad.get("energyClassification")
    dpe = dpe.upper() if isinstance(dpe, str) and dpe.upper() in _VALID_DPE else None

    year = ad.get("yearOfConstruction")
    construction_year = int(year) if isinstance(year, (int, float)) and 1600 <= year <= 2100 else None

    try:
        return PropertyListing(
            id=generate_stable_id(SOURCE_NAME, str(ad["id"])),
            source=SOURCE_NAME,
            city=canonical_city(ad.get("city")),
            district=canonical_district(district_name, ad.get("city")),
            postal_code=postal_code,
            property_type=property_type,
            surface_m2=surface,
            price_total=price,
            dpe=dpe,
            construction_year=construction_year,
            **_extract_amenities(ad),
        )
    except (KeyError, TypeError):
        return None


@register("bienici")
class BieniciScraper:
    city: str = "Metz"

    def scrape(self) -> "list[PropertyListing]":
        zone_ids = discover_zone_ids(self.city)
        if not zone_ids:
            return []

        results = []
        seen = set()
        for min_area, max_area in SURFACE_BUCKETS:
            for page in range(MAX_PAGES):
                data = fetch_json(
                    ADS_URL,
                    params=_build_filters(zone_ids, page, min_area, max_area),
                )
                if not data:
                    logger.warning("Bienici: no response (area %s-%s, page %d).",
                                   min_area, max_area, page)
                    break

                ads = data.get("realEstateAds", [])
                if not ads:
                    break

                for ad in ads:
                    listing = _parse_listing(ad)
                    if listing and listing.id not in seen:
                        seen.add(listing.id)
                        results.append(listing)

                if len(ads) < PAGE_SIZE:
                    break

        logger.info("Bienici: %d listings collected for '%s' (%d tranches surface).",
                    len(results), self.city, len(SURFACE_BUCKETS))
        return results
