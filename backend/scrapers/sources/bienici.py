import json
import logging
from typing import Optional

from scrapers.base import fetch_json, generate_stable_id
from scrapers.models import PropertyListing
from scrapers.registry import register

logger = logging.getLogger(__name__)

SOURCE_NAME = "bienici"
API_URL = "https://www.bienici.com/realEstateAds.json"

PAGE_SIZE = 50
MAX_PAGES = 5  # 250 annonces max par run — à ajuster selon besoin

_PROPERTY_TYPE_MAP = {
    "flat": "appartement",
    "studio": "appartement",
    "loft": "appartement",
    "house": "maison",
    "villa": "maison",
    "castle": "maison",
}


def _build_filters(city: str, page: int) -> dict:
    return {
        "filters": json.dumps({
            "size": PAGE_SIZE,
            "from": page * PAGE_SIZE,
            "filters": {
                "adType": "sale",
                "propertyType": list(_PROPERTY_TYPE_MAP.keys()),
                "city": city,
            }
        })
    }


def _parse_listing(ad: dict) -> Optional[PropertyListing]:
    try:
        price = float(ad["price"])
        surface = float(ad["surface"])

        if price <= 0 or surface <= 0:
            return None

        raw_type = ad.get("propertyType", "")
        property_type = _PROPERTY_TYPE_MAP.get(raw_type, "appartement")

        return PropertyListing(
            id=generate_stable_id(SOURCE_NAME, str(ad["id"])),
            source=SOURCE_NAME,
            city=ad.get("city", "").capitalize(),
            district=ad.get("district"),
            property_type=property_type,
            surface_m2=surface,
            price_total=price,
        )
    except (KeyError, ValueError, TypeError):
        return None


@register("bienici")
class BieniciScraper:
    city: str = "metz"

    def scrape(self) -> "list[PropertyListing]":
        results = []

        for page in range(MAX_PAGES):
            data = fetch_json(API_URL, params=_build_filters(self.city, page))

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

        logger.info("Bienici: %d listings collected for '%s'.", len(results), self.city)
        return results
