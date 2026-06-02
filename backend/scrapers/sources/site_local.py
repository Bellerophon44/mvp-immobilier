import logging
import re
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scrapers.base import (
    canonical_city,
    extract_construction_year,
    extract_dpe,
    fetch_page,
    generate_stable_id,
    normalize_price,
)
from scrapers.models import PropertyListing
from scrapers.registry import register

logger = logging.getLogger(__name__)

SOURCE_NAME = "laveine_immo"
BASE_URL = "https://www.laveine.immo/vente/{page}"
MAX_PAGES = 10

_PROPERTY_TYPE_MAP = {
    "appartement": "appartement",
    "studio": "appartement",
    "loft": "appartement",
    "maison": "maison",
    "villa": "maison",
    "propriete": "maison",
    "propriété": "maison",
    "chalet": "maison",
    "corps de ferme": "maison",
}


def _extract_id(card) -> Optional[str]:
    btn = card.select_one("[data-add-url]")
    if btn:
        match = re.search(r"idbien=(\d+)", btn.get("data-add-url", ""))
        if match:
            return match.group(1)
    link = card.select_one("a[href]")
    if link:
        return urlparse(link["href"]).path
    return None


def _extract_surface(title_text: str) -> Optional[float]:
    match = re.search(r"(\d[\d\s]*)\s*m²", title_text)
    if match:
        try:
            return float(match.group(1).replace(" ", "").replace("\xa0", ""))
        except ValueError:
            pass
    return None


def _extract_property_type(title_text: str) -> str:
    lowered = title_text.lower()
    for key, value in _PROPERTY_TYPE_MAP.items():
        if key in lowered:
            return value
    return "appartement"


def _extract_city(city_text: str) -> str:
    # "Courcelles-Chaussy (57530)" → "Courcelles-Chaussy"
    return re.sub(r"\s*\(\d+\)\s*$", "", city_text).strip()


def _parse_card(card) -> Optional[PropertyListing]:
    try:
        external_id = _extract_id(card)
        if not external_id:
            return None

        price_el = card.select_one(".item__price")
        title_el = card.select_one(".item__block--title")
        city_el = card.select_one(".item__block--city")

        if not price_el or not title_el or not city_el:
            return None

        price = normalize_price(price_el.get_text(strip=True))
        title_text = title_el.get_text(" ", strip=True)
        surface = _extract_surface(title_text)

        if not price or not surface:
            return None

        card_text = card.get_text(" ", strip=True)

        return PropertyListing(
            id=generate_stable_id(SOURCE_NAME, external_id),
            source=SOURCE_NAME,
            city=canonical_city(_extract_city(city_el.get_text(strip=True))),
            property_type=_extract_property_type(title_text),
            surface_m2=surface,
            price_total=price,
            dpe=extract_dpe(card_text),
            construction_year=extract_construction_year(card_text),
        )

    except Exception:
        return None


@register("laveine_immo")
class SiteLocalScraper:
    def scrape(self) -> list:
        results = []

        for page in range(1, MAX_PAGES + 1):
            html = fetch_page(BASE_URL.format(page=page))
            if not html:
                logger.warning("Laveine: no response on page %d.", page)
                break

            cards = BeautifulSoup(html, "html.parser").select("article.item")
            if not cards:
                break

            for card in cards:
                listing = _parse_card(card)
                if listing:
                    results.append(listing)

            if len(cards) < 20:
                break

        logger.info("Laveine: %d listings collected.", len(results))
        return results
