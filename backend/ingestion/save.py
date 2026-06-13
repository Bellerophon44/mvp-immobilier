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

# Re-link "sans photo" meme agence (increment 2a) — fenetre de reapparition d'un
# bien delisté (jours revolus, sens conservateur) et tolerance de surface pour la
# corroboration d'attributs. Bornes prudentes, recalibrables (cf. SPEC §7).
LINEAGE_WINDOW_DAYS = 90
LINEAGE_SURFACE_TOLERANCE = 0.02


def _norm_ref(value: Any) -> str:
    """Reference de mandat normalisee pour la comparaison : str strippe, "" si
    absente/triviale (None, vide, espaces)."""
    if value is None:
        return ""
    return str(value).strip()


def _find_lineage_candidate(db, ad: Dict[str, Any], canonical: str, now: datetime):
    """Cherche l'unique comparable disparu auquel rattacher une annonce neuve
    (re-publication meme agence). Conservateur : tout doute (reference triviale,
    plusieurs candidats, attributs trop ecartes) => None (nouvelle lignee).

    Lecture seule (`db.query`, aucun `db.add`) : robuste a l'ordre du batch et
    sans aggravation du cas id duplique intra-batch (SPEC §3.6).
    """
    reference = _norm_ref(ad.get("reference"))
    if not reference:
        return None  # reference absente/triviale => pas de recherche (§3.3.1)

    source = ad.get("source")
    surface = ad.get("surface_m2")
    if not surface or surface <= 0:
        return None

    # bienici multiplexe plusieurs agences : customer_id requis et egal pour
    # lever l'ambiguite d'une reference qui collisionne entre agences (§3.3.7).
    is_bienici = source == "bienici"
    ad_customer = _norm_ref(ad.get("customer_id"))
    if is_bienici and not ad_customer:
        return None

    candidates = (
        db.query(Comparable)
        .filter(
            Comparable.reference == reference,
            Comparable.source == source,
            Comparable.property_type == ad.get("property_type"),
            Comparable.city == canonical,
            Comparable.last_seen_at.isnot(None),
        )
        .all()
    )

    matches = []
    for cand in candidates:
        if (now - cand.last_seen_at).days > LINEAGE_WINDOW_DAYS:
            continue
        if not cand.surface_m2:
            continue
        if abs(cand.surface_m2 - surface) > LINEAGE_SURFACE_TOLERANCE * cand.surface_m2:
            continue
        if is_bienici:
            cand_customer = _norm_ref(cand.customer_id)
            if not cand_customer or cand_customer != ad_customer:
                continue
        matches.append(cand)

    # 0 => nouvelle lignee ; >=2 => abstention (ambiguite) ; 1 => rattachement.
    if len(matches) == 1:
        return matches[0]
    return None


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
                # Re-link "sans photo" meme agence (increment 2a) : un bien
                # delisté qui reapparait sous un nouvel id stable est rattache a
                # sa lignee pour prolonger l'historique de prix. La recherche est
                # conservatrice (aucun faux lien) ; sinon nouvelle lignee.
                candidate = _find_lineage_candidate(db, ad, city, now)
                if candidate is not None:
                    lineage_id = candidate.lineage_id or candidate.id  # repli heritage
                    first_seen = (
                        candidate.first_seen_at or candidate.collected_at or now
                    )
                else:
                    lineage_id = ad["id"]  # nouvelle lignee (sur elle-meme)
                    first_seen = now
                write_snapshot = True
            else:
                # Re-observation d'un id connu : comportement inc.1 inchange, le
                # lineage_id deja pose est relu tel quel (jamais re-detecte).
                lineage_id = existing.lineage_id or existing.id
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
                reference=ad.get("reference"),
                customer_id=ad.get("customer_id"),
                lineage_id=lineage_id,
                collected_at=now,
                first_seen_at=first_seen,
                last_seen_at=now,
            )

            if existing is None:
                db.add(Comparable(id=ad["id"], **fields))
                # Flush immediat : sans lui, session autoflush=False, un meme id
                # apparaissant deux fois dans le batch ne serait pas vu par le
                # db.get du second passage (identity map alimentee au flush) -> un
                # 2e db.add du meme PK ferait echouer tout le commit en
                # IntegrityError. Le flush rend l'id visible -> le doublon
                # intra-batch emprunte la branche `existing is not None`
                # (comportement attendu inc.1, AC40), sans nouvel etat memoire.
                db.flush()
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
