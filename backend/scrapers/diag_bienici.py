"""
Diagnostic du scraper Bien'ici — test de variantes de filtre géographique.

Usage (depuis backend/) :
    python -m scrapers.diag_bienici

Constat précédent : le filtre {"city": "metz"} est IGNORÉ par l'API
(total = 938 686, annonces hors Metz). Bien'ici filtre par identifiant
de zone (INSEE). Ce script teste plusieurs formats de filtre et indique
lequel restreint réellement les résultats à Metz.

Aucune écriture en base. Le bon filtre = total qui chute (centaines, pas
~900 000) ET des codes postaux 57xxx.
"""

import json
from collections import Counter

from scrapers.base import fetch_json
from scrapers.sources.bienici import API_URL

METZ_INSEE = "57463"
PROPERTY_TYPES = ["house", "flat"]


def _wrap(inner: dict) -> dict:
    """L'API attend ?filters=<json url-encodé>."""
    return {"filters": json.dumps(inner)}


# Variantes de filtre à éprouver
VARIANTS = {
    "A_buy_zone_minus": {
        "size": 50, "from": 0,
        "filterType": "buy",
        "propertyType": PROPERTY_TYPES,
        "zoneIdsByTypes": {"zoneIds": [f"-{METZ_INSEE}"]},
    },
    "B_buy_zone_plain": {
        "size": 50, "from": 0,
        "filterType": "buy",
        "propertyType": PROPERTY_TYPES,
        "zoneIdsByTypes": {"zoneIds": [METZ_INSEE]},
    },
    "C_buy_zone_minus_onmarket": {
        "size": 50, "from": 0,
        "filterType": "buy",
        "propertyType": PROPERTY_TYPES,
        "onTheMarket": [True],
        "newProperty": False,
        "zoneIdsByTypes": {"zoneIds": [f"-{METZ_INSEE}"]},
    },
    "D_sale_zone_minus": {
        "size": 50, "from": 0,
        "adType": "sale",
        "propertyType": PROPERTY_TYPES,
        "zoneIdsByTypes": {"zoneIds": [f"-{METZ_INSEE}"]},
    },
    "E_buy_postalcode": {
        "size": 50, "from": 0,
        "filterType": "buy",
        "propertyType": PROPERTY_TYPES,
        "postalCodes": ["57000", "57050", "57070"],
    },
}


def test_variant(name: str, inner: dict) -> None:
    print("\n" + "=" * 70)
    print(f"VARIANTE : {name}")
    print(f"filtre   : {json.dumps(inner, ensure_ascii=False)}")
    print("-" * 70)

    data = fetch_json(API_URL, params=_wrap(inner))
    if not isinstance(data, dict):
        print(f"  -> réponse inexploitable ({type(data).__name__})")
        return

    total = data.get("total")
    ads = data.get("realEstateAds", [])
    print(f"total API : {total}   |   annonces page : {len(ads)}")

    if total and total > 100000:
        print("  -> filtre IGNORÉ (total ~ catalogue entier).")

    cps = Counter()
    print("  8 premières annonces :")
    for ad in ads[:8]:
        city = ad.get("city")
        cp = ad.get("postalCode")
        ptype = ad.get("propertyType")
        price = ad.get("price")
        surf = ad.get("surfaceArea")
        cps[str(cp)[:2]] += 1
        print(f"    {str(city)[:22]:22} {str(cp):8} {str(ptype):10} "
              f"{str(price):>10} € {str(surf):>7} m²")

    dep57 = cps.get("57", 0)
    verdict = "✅ MOSELLE (57) majoritaire" if dep57 >= 5 else \
              "⚠️ pas de concentration 57xxx"
    print(f"  Codes postaux dépt : {dict(cps)}  -> {verdict}")


def main() -> None:
    print("Test des variantes de filtre Bien'ici pour Metz (INSEE",
          METZ_INSEE, ")")
    for name, inner in VARIANTS.items():
        test_variant(name, inner)
    print("\n" + "=" * 70)
    print("La bonne variante = total faible + codes postaux 57xxx.")
    print("Colle toute la sortie pour figer le filtre définitif.")


if __name__ == "__main__":
    main()
