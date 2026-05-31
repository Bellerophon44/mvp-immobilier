import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from scrapers.base import (
    fetch_page,
    generate_stable_id,
    infer_property_type,
    normalize_price,
    normalize_surface,
)
from scrapers.models import PropertyListing
from scrapers.registry import register

logger = logging.getLogger(__name__)

SOURCE_NAME = "benedic"
BASE_URL = "https://www.benedicsa.com/particuliers/ventes"
MAX_PAGES = 15

# Slug de l'annonce, ex : "maison-fameck-5-pieces-102-40-m2-10181"
#   type(maison) - ville(fameck) - N pieces - surface(102-40 -> 102.40) - id
_SLUG_RE = re.compile(
    r"/ventes/([a-z]+)-(.+?)-\d+-pieces?-([\d-]+)-m2-(\d+)", re.IGNORECASE
)

_PROPERTY_TYPE_MAP = {
    "appartement": "appartement",
    "studio": "appartement",
    "maison": "maison",
    "villa": "maison",
    "propriete": "maison",
    "ferme": "maison",
    "immeuble": "maison",
}


def _slug_city(slug: str) -> str:
    return " ".join(p.capitalize() for p in slug.split("-"))


def _slug_surface(raw: str) -> Optional[float]:
    # "102-40" -> 102.40 ; "86" -> 86
    return normalize_surface(raw.replace("-", ".", 1))


def _parse_card(card) -> Optional[PropertyListing]:
    try:
        external_id = card.get("data-card-maker")
        link = card.select_one("a[href*='/ventes/']")
        if not external_id or not link:
            return None

        text = card.get_text(" ", strip=True)
        price = normalize_price(text) if "€" in text else None

        type_from_slug = city = None
        surface = None
        m = _SLUG_RE.search(link["href"])
        if m:
            type_from_slug = _PROPERTY_TYPE_MAP.get(m.group(1).lower())
            city = _slug_city(m.group(2))
            surface = _slug_surface(m.group(3))

        if surface is None:
            sm = re.search(r"(\d+(?:[.,]\d+)?)\s*m[²2]", text, re.IGNORECASE)
            surface = normalize_surface(sm.group(0)) if sm else None

        property_type = type_from_slug or infer_property_type(text)

        if not price or not surface or not city:
            return None

        return PropertyListing(
            id=generate_stable_id(SOURCE_NAME, external_id),
            source=SOURCE_NAME,
            city=city,
            property_type=property_type,
            surface_m2=surface,
            price_total=price,
        )
    except Exception:
        return None


@register("benedic")
class BenedicScraper:
    def scrape(self) -> list:
        results = []
        seen = set()

        for page in range(1, MAX_PAGES + 1):
            url = BASE_URL if page == 1 else f"{BASE_URL}?page={page}"
            html = fetch_page(url)
            if not html:
                logger.warning("Benedic: no response on page %d.", page)
                break

            cards = BeautifulSoup(html, "html.parser").select("[data-card-maker]")
            if not cards:
                break

            new_on_page = 0
            for card in cards:
                listing = _parse_card(card)
                if listing and listing.id not in seen:
                    seen.add(listing.id)
                    results.append(listing)
                    new_on_page += 1

            # Pagination inconnue : on s'arrête dès qu'une page n'apporte aucune
            # annonce nouvelle (page renvoyée à l'identique = param ignoré).
            if new_on_page == 0:
                break

        logger.info("Benedic: %d listings collected.", len(results))
        return results
