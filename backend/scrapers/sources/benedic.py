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

SOURCE_NAME = "benedic"
BASE_URL = "https://www.benedicsa.com/particuliers/ventes"
MAX_PAGES = 15

_PROPERTY_TYPE_MAP = {
    "appartement": "appartement",
    "studio": "appartement",
    "maison": "maison",
    "villa": "maison",
    "propriete": "maison",
    "ferme": "maison",
    "immeuble": "maison",
}

_SURFACE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*m[²2]", re.IGNORECASE)


def _property_type(title: str) -> str:
    lowered = title.lower()
    for key, value in _PROPERTY_TYPE_MAP.items():
        if key in lowered:
            return value
    return infer_property_type(title)


def _extract_surface(*texts: str) -> Optional[float]:
    for text in texts:
        match = _SURFACE_RE.search(text or "")
        if match:
            return normalize_surface(match.group(0))
    return None


def _parse_card(card) -> Optional[PropertyListing]:
    try:
        external_id = card.get("data-card-maker")
        price_el = card.select_one("p.text-2xl")
        city_el = card.select_one("p.uppercase")
        if not external_id or not price_el or not city_el:
            return None

        # Le prix est isolé dans son <p> dédié : on ne lit PAS le texte global de
        # la carte (le premier nombre y est le compteur de photos, pas le prix).
        price = normalize_price(price_el.get_text(strip=True))
        # La pastille ville est parfois préfixée d'une zone ("Metz Métropole -
        # Metz") : on garde le dernier segment pour s'aligner sur les autres
        # sources et permettre l'agrégation des comparables par ville.
        city = canonical_city(city_el.get_text(" ", strip=True).split(" - ")[-1])

        title_el = card.select_one("h2.thumb__title")
        meta_el = card.select_one("div.text-base")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        meta = meta_el.get_text(" ", strip=True) if meta_el else ""
        surface = _extract_surface(meta, title)

        if not price or not surface or not city:
            return None

        card_text = card.get_text(" ", strip=True)

        return PropertyListing(
            id=generate_stable_id(SOURCE_NAME, external_id),
            source=SOURCE_NAME,
            city=city,
            property_type=_property_type(title),
            surface_m2=surface,
            price_total=price,
            dpe=extract_dpe(card_text),
            construction_year=extract_construction_year(card_text),
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
            # annonce nouvelle (param ignoré = page renvoyée a l'identique).
            if new_on_page == 0:
                break

        logger.info("Benedic: %d listings collected.", len(results))
        return results
