import json
import logging
from typing import Optional

from scrapers.base import (
    fetch_json,
    generate_stable_id,
    canonical_city,
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
MAX_PAGES = 20  # jusqu'à 1000 annonces brutes par run avant filtrage

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


def _build_filters(zone_ids: list, page: int) -> dict:
    return {
        "filters": json.dumps({
            "size": PAGE_SIZE,
            "from": page * PAGE_SIZE,
            "filterType": "buy",
            "propertyType": list(_PROPERTY_TYPE_MAP.keys()),
            "zoneIdsByTypes": {"zoneIds": zone_ids},
        })
    }


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

    try:
        return PropertyListing(
            id=generate_stable_id(SOURCE_NAME, str(ad["id"])),
            source=SOURCE_NAME,
            city=canonical_city(ad.get("city")),
            district=district_name,
            property_type=property_type,
            surface_m2=surface,
            price_total=price,
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
        for page in range(MAX_PAGES):
            data = fetch_json(ADS_URL, params=_build_filters(zone_ids, page))
            if not data:
                logger.warning("Bienici: no response on page %d.", page)
                break

            ads = data.get("realEstateAds", [])
            if not ads:
                break

            for ad in ads:
                listing = _parse_listing(ad)
                if listing:
                    results.append(listing)

            if len(ads) < PAGE_SIZE:
                break

        logger.info("Bienici: %d listings collected for '%s'.",
                    len(results), self.city)
        return results
