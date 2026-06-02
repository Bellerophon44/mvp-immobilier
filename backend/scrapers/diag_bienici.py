"""
Diagnostic du scraper Bien'ici — confirmation du filtre par zoneIds.

Découverte clé : l'endpoint suggest renvoie pour Metz
    {"name": "Metz", "type": "city", "zoneIds": ["-450381"], ...}
Le bon filtre est zoneIdsByTypes.zoneIds = ["-450381"] (découvert
dynamiquement par ville, pas codé en dur).

Ce script :
  1. découvre les zoneIds de Metz via discover_zone_ids()
  2. fait un appel brut filtré et montre la couverture (dépt, échantillon)
  3. lance le scraper complet et affiche les stats

Aucune écriture en base.
"""

import json
from collections import Counter

from scrapers.base import fetch_json
from scrapers.sources.bienici import (
    ADS_URL,
    discover_zone_ids,
    _build_filters,
    BieniciScraper,
)

CITY = "Metz"


def _safe(value, max_len: int = 0) -> str:
    s = "?" if value is None else str(value)
    return s[:max_len] if max_len else s


def step1_zone() -> list:
    print("=" * 70)
    print(f"ÉTAPE 1 — Découverte des zoneIds pour '{CITY}'")
    print("-" * 70)
    zone_ids = discover_zone_ids(CITY)
    print(f"zoneIds = {zone_ids}")
    return zone_ids


def step2_raw(zone_ids: list) -> None:
    print("\n" + "=" * 70)
    print("ÉTAPE 2 — Appel brut + analyse de la pollution (page 0)")
    print("-" * 70)
    if not zone_ids:
        print("  (pas de zoneIds, on saute)")
        return
    data = fetch_json(ADS_URL, params=_build_filters(zone_ids, 0))
    if not isinstance(data, dict):
        print(f"  réponse inexploitable ({type(data).__name__})")
        return
    total = data.get("total")
    ads = data.get("realEstateAds", [])
    print(f"  total={total}   annonces page={len(ads)}")

    by_adtype = Counter(_safe(a.get("adType")) for a in ads)
    print(f"  adType (brut) : {dict(by_adtype)}")

    # Annonces au prix/m² aberrant : on montre leurs champs discriminants
    print("  Annonces suspectes (prix/m² < 800) — champs discriminants :")
    shown = 0
    for a in ads:
        price = a.get("price")
        surf = a.get("surfaceArea")
        if not isinstance(price, (int, float)) or not isinstance(surf, (int, float)):
            continue
        if surf <= 0:
            continue
        pm2 = price / surf
        if pm2 < 800 and shown < 6:
            print(f"    {pm2:7.0f} €/m² | adType={_safe(a.get('adType'))} "
                  f"transactionType={_safe(a.get('transactionType'))} "
                  f"newProperty={_safe(a.get('newProperty'))} "
                  f"| {_safe(a.get('title'), 50)}")
            shown += 1


def step3_scrape() -> None:
    print("\n" + "=" * 70)
    print("ÉTAPE 3 — Scraper complet BieniciScraper().scrape()")
    print("-" * 70)
    listings = BieniciScraper().scrape()
    print(f"Annonces valides : {len(listings)}")
    if not listings:
        return

    by_city = Counter(l.city for l in listings)
    by_type = Counter(l.property_type for l in listings)
    prices_m2 = sorted(l.price_total / l.surface_m2 for l in listings if l.surface_m2)

    print(f"villes  : {dict(by_city.most_common(8))}")
    print(f"types   : {dict(by_type)}")
    if prices_m2:
        n = len(prices_m2)
        print(f"prix/m² : min={prices_m2[0]:.0f}  médiane={prices_m2[n//2]:.0f}  "
              f"max={prices_m2[-1]:.0f} €/m²")
    print("Échantillon (5) :")
    for l in listings[:5]:
        pm2 = l.price_total / l.surface_m2 if l.surface_m2 else 0
        print(f"  [{l.property_type:11}] {l.city:18} {l.surface_m2:6.0f} m²  "
              f"{l.price_total:>10.0f} €  ({pm2:.0f} €/m²)  district={l.district}")


def step4_low_tail(zone_ids: list) -> None:
    """Ausculte la queue basse : biens résidentiels 'buy' qui passent les filtres
    actuels mais au prix/m² le plus faible. Affiche leurs champs discriminants
    pour comprendre ce qui tire la médiane Metz vers le bas (parkings/caves/lots
    déguisés ? studios dégradés ? programmes ?)."""
    print("\n" + "=" * 70)
    print("ÉTAPE 4 — Queue basse des biens valides (champs discriminants)")
    print("-" * 70)
    if not zone_ids:
        print("  (pas de zoneIds, on saute)")
        return

    rows = []
    for page in range(20):
        data = fetch_json(ADS_URL, params=_build_filters(zone_ids, page))
        if not isinstance(data, dict):
            break
        ads = data.get("realEstateAds", [])
        if not ads:
            break
        for a in ads:
            if a.get("adType") != "buy":
                continue
            price, surf = a.get("price"), a.get("surfaceArea")
            if not isinstance(price, (int, float)) or not isinstance(surf, (int, float)):
                continue
            if surf <= 0 or price <= 0:
                continue
            pm2 = price / surf
            if pm2 < 800 or pm2 > 12000:
                continue
            rows.append((pm2, price, surf, a))
        if len(ads) < 50:
            break

    if not rows:
        print("  (aucun bien)")
        return

    rows.sort(key=lambda r: r[0])
    n = len(rows)
    deciles = [rows[int(n * q / 10)][0] for q in range(1, 10)]
    print(f"  {n} biens valides. Déciles prix/m² : "
          + " ".join(f"{d:.0f}" for d in deciles))
    print("  25 biens les moins chers au m² :")
    for pm2, price, surf, a in rows[:25]:
        print(f"    {pm2:6.0f} €/m² | {price:>9.0f} € | {surf:5.0f} m² | "
              f"type={_safe(a.get('propertyType')):9} "
              f"pièces={_safe(a.get('roomsQuantity')):3} "
              f"neuf={_safe(a.get('newProperty')):5} "
              f"| {_safe(a.get('title'), 48)}")


def main() -> None:
    zone_ids = step1_zone()
    step2_raw(zone_ids)
    step3_scrape()
    step4_low_tail(zone_ids)
    print("\n" + "=" * 70)
    print("Succès attendu : total bas, dépt 57, prix/m² réalistes (~2000-3500).")


if __name__ == "__main__":
    main()
