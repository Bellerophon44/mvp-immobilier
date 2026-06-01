import logging
from datetime import datetime
from typing import List, Dict, Any

from db.session import SessionLocal, init_db
from db.models import Comparable
from scrapers.base import canonical_city

logger = logging.getLogger("ingestion")

# Garde-fou de plausibilité prix/m² pour une vente résidentielle, appliqué à
# TOUTES les sources avant écriture. Centralisé ici (et non dans chaque
# scraper) pour que toute nouvelle agence soit protégée sans y penser : éjecte
# loyers, parkings, viagers et erreurs de saisie qui pollueraient les stats.
MIN_PRICE_M2 = 800.0
MAX_PRICE_M2 = 12000.0

# Communes hors périmètre (Meurthe-et-Moselle / agglomération nancéienne)
# parfois remontées par les sources qui couvrent au-delà de la Moselle. Formes
# canoniques (cf. canonical_city). Étendre cette liste au besoin.
OUT_OF_SCOPE_CITIES = {
    "Nancy",
    "Vandœuvre-Les-Nancy",
    "Villers-Les-Nancy",
    "Jarville-La-Malgrange",
}


def save_comparables(listings: List[Dict[str, Any]]) -> int:
    """
    Sauvegarde une liste d'annonces comparables en base de données.

    Retourne le nombre d'annonces effectivement enregistrées.
    """

    if not listings:
        return 0

    # S'assurer que la DB est initialisée
    init_db()

    db = SessionLocal()
    saved_count = 0
    rejected_band = 0
    rejected_zone = 0

    for ad in listings:
        try:
            surface = ad.get("surface_m2")
            price = ad.get("price_total")

            if not surface or not price or surface <= 0:
                continue

            price_m2 = price / surface

            if price_m2 < MIN_PRICE_M2 or price_m2 > MAX_PRICE_M2:
                rejected_band += 1
                continue

            city = canonical_city(ad.get("city"))
            if city in OUT_OF_SCOPE_CITIES:
                rejected_zone += 1
                continue

            comparable = Comparable(
                id=ad["id"],
                source=ad["source"],
                city=city,
                district=ad.get("district"),
                property_type=ad["property_type"],
                surface_m2=surface,
                price_total=price,
                price_m2=price_m2,
                collected_at=datetime.utcnow()
            )

            # merge = insert ou update si déjà existant
            db.merge(comparable)
            saved_count += 1

        except Exception:
            # MVP : on ignore silencieusement les erreurs individuelles
            continue

    db.commit()
    db.close()

    if rejected_band or rejected_zone:
        logger.info(
            "Ingestion : %d rejetées hors prix/m² [%.0f-%.0f], %d hors périmètre.",
            rejected_band, MIN_PRICE_M2, MAX_PRICE_M2, rejected_zone,
        )

    return saved_count
