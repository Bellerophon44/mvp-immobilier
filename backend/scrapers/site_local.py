from typing import List, Dict, Any
from bs4 import BeautifulSoup

from scrapers.base import (
    fetch_page,
    generate_stable_id,
    normalize_price,
    normalize_surface
)

# -------------------------
# Configuration du site ciblé
# -------------------------

SOURCE_NAME = "site_local_metz"
BASE_URL = "https://www.laveine.immo/"  # À adapter


# -------------------------
# Helpers simples
# -------------------------

def infer_property_type(text: str) -> str:
    """
    Déduction très simple du type de bien à partir du texte.
    MVP volontairement grossier.
    """
    text = text.lower()
    if "maison" in text or "villa" in text or "propriété" in text:
        return "maison"
    return "appartement"


def extract_district(text: str) -> str:
    """
    Extraction basique du quartier (si présent).
    À enrichir plus tard si besoin.
    """
    known_districts = [
        "queuleu",
        "sablon",
        "centre",
        "plantières",
        "devant-les-ponts"
    ]

    lowered = text.lower()
    for district in known_districts:
        if district in lowered:
            return district.capitalize()
    return "Inconnu"


# -------------------------
# Scraper principal
# -------------------------

def scrape_site_local_metz() -> List[Dict[str, Any]]:
    """
    Scrape un site local ciblé Metz.
    Retourne une liste d’annonces normalisées.
    """

    html = fetch_page(BASE_URL)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Sélecteur générique des cartes d’annonces
    cards = soup.select(".property-card")  # ⚠️ à adapter

    for card in cards:
        try:
            # Extraction brute
            raw_price = card.select_one(".price").get_text(strip=True)
            raw_surface = card.select_one(".surface").get_text(strip=True)
            raw_title = card.get_text(" ", strip=True)

            price = normalize_price(raw_price)
            surface = normalize_surface(raw_surface)

            if not price or not surface:
                continue

            external_id = card.get("data-id") or raw_title[:50]

            results.append({
                "id": generate_stable_id(SOURCE_NAME, external_id),
                "source": SOURCE_NAME,
                "city": "Metz",
                "district": extract_district(raw_title),
                "property_type": infer_property_type(raw_title),
                "surface_m2": surface,
                "price_total": price
            })

        except Exception:
            # MVP : on ignore silencieusement les anomalies
            continue

    return results
