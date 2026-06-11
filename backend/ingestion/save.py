import logging
from datetime import datetime
from typing import List, Dict, Any

from db.session import SessionLocal, init_db
from db.models import Comparable, ListingPriceSnapshot
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

# Filtre de périmètre fiable quand le code postal est connu : on ne garde que la
# Moselle (dépt 57). Complète OUT_OF_SCOPE_CITIES (blocklist de noms), qui reste
# le seul recours pour les sources sans code postal. N'écarte JAMAIS un bien dont
# le code postal est absent — sinon on perdrait les sources qui ne l'exposent pas.
IN_SCOPE_DEPARTMENT = "57"


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

            postal_code = ad.get("postal_code")
            if postal_code and not postal_code.startswith(IN_SCOPE_DEPARTMENT):
                rejected_zone += 1
                continue

            now = datetime.utcnow()

            # Lecture explicite de la ligne existante (et non db.merge, qui
            # reconstruirait un objet detache et ecraserait first_seen_at) :
            # le tracking temporel exige de relire l'historique avant d'ecrire.
            existing = db.get(Comparable, ad["id"])

            if existing is None:
                first_seen = now
                write_snapshot = True
            else:
                # first_seen_at immuable ; repli collected_at pour les lignes
                # prod heritees d'avant cet increment (first_seen_at NULL).
                first_seen = existing.first_seen_at or existing.collected_at or now
                # Egalite exacte voulue : price_total est un parsing
                # deterministe (entiers euros), une tolerance serait de la
                # fausse precision. On ne compare pas price_m2 (derive de la
                # surface, instable au reparsing).
                write_snapshot = existing.price_total != price

            fields = dict(
                source=ad["source"],
                city=city,
                district=ad.get("district"),
                postal_code=postal_code,
                property_type=ad["property_type"],
                surface_m2=surface,
                price_total=price,
                price_m2=price_m2,
                dpe=ad.get("dpe"),
                construction_year=ad.get("construction_year"),
                floor=ad.get("floor"),
                has_elevator=ad.get("has_elevator"),
                has_terrace=ad.get("has_terrace"),
                has_balcony=ad.get("has_balcony"),
                is_condo=ad.get("is_condo"),
                condo_fees=ad.get("condo_fees"),
                has_cellar=ad.get("has_cellar"),
                parking=ad.get("parking"),
                bedrooms=ad.get("bedrooms"),
                collected_at=now,
                first_seen_at=first_seen,
                last_seen_at=now,
            )

            if existing is None:
                db.add(Comparable(id=ad["id"], **fields))
            else:
                for key, value in fields.items():
                    setattr(existing, key, value)

            if write_snapshot:
                db.add(ListingPriceSnapshot(
                    listing_id=ad["id"],
                    price_total=price,
                    price_m2=price_m2,
                    observed_at=now,
                ))

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
