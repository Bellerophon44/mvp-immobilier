import logging
from datetime import datetime
from typing import List, Dict, Any

from db.session import SessionLocal, init_db
from db.models import Comparable

logger = logging.getLogger("ingestion")

# Garde-fou de plausibilité prix/m² pour une vente résidentielle, appliqué à
# TOUTES les sources avant écriture. Centralisé ici (et non dans chaque
# scraper) pour que toute nouvelle agence soit protégée sans y penser : éjecte
# loyers, parkings, viagers et erreurs de saisie qui pollueraient les stats.
MIN_PRICE_M2 = 800.0
MAX_PRICE_M2 = 12000.0


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

            comparable = Comparable(
                id=ad["id"],
                source=ad["source"],
                city=ad["city"],
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

    if rejected_band:
        logger.info(
            "Ingestion : %d annonces rejetées (prix/m² hors [%.0f-%.0f]).",
            rejected_band, MIN_PRICE_M2, MAX_PRICE_M2,
        )

    return saved_count
