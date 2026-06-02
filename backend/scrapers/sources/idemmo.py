import logging
import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapers.base import (
    canonical_city,
    extract_construction_year,
    fetch_page,
    generate_stable_id,
    infer_property_type,
    normalize_price,
    normalize_surface,
)

_VALID_DPE = {"A", "B", "C", "D", "E", "F", "G"}
from scrapers.models import PropertyListing
from scrapers.registry import register

logger = logging.getLogger(__name__)

SOURCE_NAME = "idemmo"
# Listing "ventes" du site idemmo.fr (plugin WordPress Essential Real Estate).
START_URL = "https://idemmo.fr/rechercher/?es=1&address&es_category=6"
MAX_PAGES = 15


def _extract_external_id(href: str) -> Optional[str]:
    # .../hayange-...-87020413/?search_url=... -> 87020413
    match = re.search(r"-(\d+)/?(?:\?|$)", href.split("?")[0])
    return match.group(1) if match else (href.split("?")[0] or None)


def _meta_text(card, css_class: str) -> Optional[str]:
    el = card.select_one(f"li.{css_class} .es-listing__meta_text")
    return el.get_text(strip=True) if el else None


def _parse_card(card) -> Optional[PropertyListing]:
    try:
        link = card.select_one("h3.es-listing__title a[href]")
        price_el = card.select_one(".es-price")
        if not link or not price_el:
            return None

        href = link["href"]
        external_id = _extract_external_id(href)
        if not external_id:
            return None

        price = normalize_price(price_el.get_text(strip=True))
        surface_raw = _meta_text(card, "es_property_area")
        surface = normalize_surface(surface_raw) if surface_raw else None
        if not price or not surface:
            return None

        city = _meta_text(card, "es_property_address")
        if not city:
            return None

        title_text = link.get_text(" ", strip=True)
        dpe_raw = _meta_text(card, "es_property_dpe_energie_lettre")
        dpe = dpe_raw.upper() if dpe_raw and dpe_raw.upper() in _VALID_DPE else None

        return PropertyListing(
            id=generate_stable_id(SOURCE_NAME, external_id),
            source=SOURCE_NAME,
            city=canonical_city(city),
            property_type=infer_property_type(title_text),
            surface_m2=surface,
            price_total=price,
            dpe=dpe,
            construction_year=extract_construction_year(title_text),
        )
    except Exception:
        return None


def _next_page_url(soup, current_url: str) -> Optional[str]:
    nxt = soup.select_one(
        "a.next.page-numbers, a.page-numbers.next, .es-pagination a[rel='next']"
    )
    if nxt and nxt.get("href"):
        return urljoin(current_url, nxt["href"])
    return None


@register("idemmo")
class IdemmoScraper:
    def scrape(self) -> list:
        results = []
        seen = set()
        url = START_URL

        for _ in range(MAX_PAGES):
            html = fetch_page(url)
            if not html:
                logger.warning("Idemmo: no response on %s.", url)
                break

            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select("div.js-es-listing")
            if not cards:
                break

            new_on_page = 0
            for card in cards:
                listing = _parse_card(card)
                if listing and listing.id not in seen:
                    seen.add(listing.id)
                    results.append(listing)
                    new_on_page += 1

            next_url = _next_page_url(soup, url)
            if not next_url or new_on_page == 0:
                break
            url = next_url

        logger.info("Idemmo: %d listings collected.", len(results))
        return results
