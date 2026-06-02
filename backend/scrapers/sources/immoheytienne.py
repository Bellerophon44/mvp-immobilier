import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from scrapers.base import (
    canonical_city,
    extract_construction_year,
    extract_dpe,
    fetch_page,
    generate_stable_id,
    infer_property_type,
    normalize_price,
    normalize_surface,
)
from scrapers.models import PropertyListing
from scrapers.registry import register

logger = logging.getLogger(__name__)

SOURCE_NAME = "immoheytienne"
BASE_URL = "https://immoheytienne.fr/fr/properties"
MAX_PAGES = 15

_SURFACE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*m", re.IGNORECASE)


def _extract_id(href: str) -> Optional[str]:
    # "/fr/property/a-vendre-maison-metz--5524910" -> 5524910
    match = re.search(r"-(\d+)/?$", href)
    return match.group(1) if match else (href or None)


def _extract_surface(card) -> Optional[float]:
    # La surface habitable est dans un span "picto" (ex. "118 m²"). On évite le
    # titre, qui contient des pièges ("jardin 408 m²", année "1933").
    for span in card.select("span.text-lowercase"):
        text = span.get_text(" ", strip=True).lower()
        if "pièce" in text or "chambre" in text:
            continue
        match = _SURFACE_RE.search(text)
        if match:
            return normalize_surface(match.group(1))
    return None


def _parse_card(card) -> Optional[PropertyListing]:
    try:
        href = card.get("href", "")
        external_id = _extract_id(href)
        price_el = card.select_one(".price-badge")
        city_el = card.select_one(".locality-badge")
        if not external_id or not price_el or not city_el:
            return None

        price = normalize_price(price_el.get_text(strip=True))
        surface = _extract_surface(card)
        city = canonical_city(city_el.get_text(" ", strip=True))
        if not price or not surface or not city:
            return None

        card_text = card.get_text(" ", strip=True)

        return PropertyListing(
            id=generate_stable_id(SOURCE_NAME, external_id),
            source=SOURCE_NAME,
            city=city,
            property_type=infer_property_type(href),
            surface_m2=surface,
            price_total=price,
            dpe=extract_dpe(card_text),
            construction_year=extract_construction_year(card_text),
        )
    except Exception:
        return None


@register("immoheytienne")
class ImmoHeytienneScraper:
    def scrape(self) -> list:
        results = []
        seen = set()

        for page in range(1, MAX_PAGES + 1):
            url = BASE_URL if page == 1 else f"{BASE_URL}?page={page}"
            html = fetch_page(url)
            if not html:
                logger.warning("ImmoHeytienne: no response on page %d.", page)
                break

            cards = BeautifulSoup(html, "html.parser").select(
                "a.text-decoration-none[href*='/property/']"
            )
            if not cards:
                break

            new_on_page = 0
            for card in cards:
                listing = _parse_card(card)
                if listing and listing.id not in seen:
                    seen.add(listing.id)
                    results.append(listing)
                    new_on_page += 1

            if new_on_page == 0:
                break

        logger.info("ImmoHeytienne: %d listings collected.", len(results))
        return results
