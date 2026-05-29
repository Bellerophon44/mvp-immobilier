"""
Diagnostic du scraper Bien'ici.

Usage (depuis backend/) :
    python -m scrapers.diag_bienici

Le script ne touche pas la base. Il :
  1. fait un appel brut à l'API Bien'ici (page 0) et inspecte la réponse
     (présence de données, nombre d'annonces, champs disponibles) ;
  2. lance le scraper complet BieniciScraper().scrape() ;
  3. affiche la couverture : nombre d'annonces, répartition par ville,
     fourchettes de surface / prix / prix au m².

Objectif : valider si l'API renvoie bien des annonces pour Metz, et si
le paramètre 'city' filtre correctement (sinon coverage = 0).
"""

import json
from collections import Counter

from scrapers.base import fetch_json
from scrapers.sources.bienici import (
    API_URL,
    PAGE_SIZE,
    _build_filters,
    BieniciScraper,
)


def step_raw_call() -> None:
    print("=" * 70)
    print("ÉTAPE 1 — Appel API brut (page 0)")
    print("-" * 70)
    print(f"URL    : {API_URL}")
    params = _build_filters("metz", 0)
    print(f"params : {params}")

    data = fetch_json(API_URL, params=params)
    if data is None:
        print("RÉSULTAT : aucune réponse exploitable (None).")
        print("  -> soit l'API bloque la requête, soit la réponse n'est pas du JSON.")
        return

    if not isinstance(data, dict):
        print(f"RÉSULTAT : réponse JSON de type {type(data).__name__} (inattendu).")
        print(json.dumps(data, ensure_ascii=False)[:500])
        return

    print(f"Clés racine : {list(data.keys())}")
    total = data.get("total")
    ads = data.get("realEstateAds", [])
    print(f"total (champ API) : {total}")
    print(f"annonces dans cette page : {len(ads)} (page_size attendu={PAGE_SIZE})")

    if ads:
        sample = ads[0]
        print("\nChamps de la 1re annonce :")
        print(f"  {sorted(sample.keys())}")
        print("\nValeurs clés de la 1re annonce :")
        for k in ("id", "price", "surface", "propertyType", "city", "district",
                  "postalCode", "title"):
            print(f"  {k:14} = {sample.get(k)!r}")
    else:
        print("\nAUCUNE annonce dans la réponse.")
        print("  -> le paramètre 'city=metz' ne filtre probablement pas comme attendu")
        print("     (Bien'ici attend souvent un identifiant de zone, pas un nom).")


def step_full_scrape() -> None:
    print("\n" + "=" * 70)
    print("ÉTAPE 2 — Scraper complet BieniciScraper().scrape()")
    print("-" * 70)

    listings = BieniciScraper().scrape()
    print(f"Annonces parsées et valides : {len(listings)}")

    if not listings:
        print("  -> 0 annonce exploitable. Voir l'étape 1 pour la cause.")
        return

    by_city = Counter(l.city for l in listings)
    surfaces = [l.surface_m2 for l in listings]
    prices = [l.price_total for l in listings]
    prices_m2 = [l.price_total / l.surface_m2 for l in listings if l.surface_m2]

    print("\nRépartition par ville :")
    for city, n in by_city.most_common(10):
        print(f"  {city or '(vide)':28} {n}")

    def _range(label, values, unit):
        if not values:
            print(f"  {label}: n/a")
            return
        print(f"  {label}: min={min(values):.0f}{unit} "
              f"médiane≈{sorted(values)[len(values)//2]:.0f}{unit} "
              f"max={max(values):.0f}{unit}")

    print("\nFourchettes :")
    _range("surface", surfaces, "m²")
    _range("prix", prices, "€")
    _range("prix/m²", prices_m2, "€/m²")

    print("\nÉchantillon (5 premières) :")
    for l in listings[:5]:
        pm2 = (l.price_total / l.surface_m2) if l.surface_m2 else 0
        print(f"  [{l.property_type:11}] {l.city:20} "
              f"{l.surface_m2:6.0f} m²  {l.price_total:>10.0f} €  "
              f"({pm2:.0f} €/m²)  district={l.district}")


def main() -> None:
    step_raw_call()
    step_full_scrape()
    print("\n" + "=" * 70)
    print("Diagnostic terminé. Colle toute cette sortie pour décider de la suite.")


if __name__ == "__main__":
    main()
