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
    PAGE_SIZE,
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


def _collect_valid_rows(zone_ids: list) -> list:
    """Biens résidentiels 'buy' qui passent les filtres prix/m² actuels, avec
    leur ad brut (pour les champs discriminants)."""
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
            if 800 <= pm2 <= 12000:
                rows.append((pm2, price, surf, a))
        if len(ads) < 50:
            break
    rows.sort(key=lambda r: r[0])
    return rows


def low_price_tail_md(city: str = CITY) -> str:
    """Markdown : queue basse des biens valides (pour le harnais de diagnostic).
    Révèle ce qui tire la médiane vers le bas avant de resserrer les filtres."""
    zone_ids = discover_zone_ids(city)
    if not zone_ids:
        return f"## Queue basse bienici ({city})\n\n_(pas de zoneId)_\n"
    rows = _collect_valid_rows(zone_ids)
    if not rows:
        return f"## Queue basse bienici ({city})\n\n_(aucun bien)_\n"

    n = len(rows)
    deciles = [rows[int(n * q / 10)][0] for q in range(1, 10)]
    lines = [
        f"## Queue basse bienici ({city}) — {n} biens valides",
        "- déciles prix/m² : " + " · ".join(f"{d:.0f}" for d in deciles),
        "- 20 biens les moins chers au m² (champs discriminants) :",
    ]
    for pm2, price, surf, a in rows[:20]:
        lines.append(
            f"  - {pm2:.0f} €/m² | {price:.0f} € | {surf:.0f} m² | "
            f"type={_safe(a.get('propertyType'))} "
            f"pièces={_safe(a.get('roomsQuantity'))} "
            f"neuf={_safe(a.get('newProperty'))} | {_safe(a.get('title'), 60)}"
        )
    return "\n".join(lines) + "\n"


def step4_low_tail(zone_ids: list) -> None:
    print("\n" + "=" * 70)
    print(low_price_tail_md())


def deep_pagination_probe_md(city: str = CITY, max_pages: int = 80) -> str:
    """Sonde : jusqu'où l'API bien'ici pagine-t-elle, et quelle distribution de
    surfaces au-delà des 1000 premières annonces ? Distingue 'pagination
    autorisée -> lever le plafond' de 'pagination plafonnée -> balayer par
    tranches de surface'."""
    zone_ids = discover_zone_ids(city)
    if not zone_ids:
        return f"## Sonde pagination bienici ({city})\n\n_(pas de zoneId)_\n"

    total = None
    fetched = 0
    buy_surfaces = []
    last_full_page = -1
    last_page_with_data = -1
    for page in range(max_pages):
        data = fetch_json(ADS_URL, params=_build_filters(zone_ids, page))
        if not isinstance(data, dict):
            break
        if total is None:
            total = data.get("total")
        ads = data.get("realEstateAds", [])
        if not ads:
            break
        fetched += len(ads)
        last_page_with_data = page
        if len(ads) >= PAGE_SIZE:
            last_full_page = page
        for a in ads:
            if a.get("adType") != "buy":
                continue
            s = a.get("surfaceArea")
            if isinstance(s, (int, float)) and not isinstance(s, bool):
                buy_surfaces.append(float(s))
        if len(ads) < PAGE_SIZE:
            break

    n = len(buy_surfaces)
    buckets = [(0, 40), (40, 55), (55, 70), (70, 85), (85, 100), (100, 1e9)]
    lines = [
        f"## Sonde pagination bienici ({city})",
        f"- total annoncé par l'API : {total}",
        f"- dernière page avec data : {last_page_with_data} · dernière page pleine : "
        f"{last_full_page} (offset atteint {(last_page_with_data + 1) * PAGE_SIZE})",
        f"- annonces brutes récupérées : {fetched} · surfaces 'buy' numériques : {n}",
    ]
    if n:
        lines.append(f"- surface buy : min={min(buy_surfaces):.0f} max={max(buy_surfaces):.0f} m²")
        lines.append("- histogramme surfaces buy (toutes pages sondées) :")
        for b_lo, b_hi in buckets:
            c = sum(1 for s in buy_surfaces if b_lo <= s < b_hi)
            label = f"{b_lo:.0f}-{b_hi:.0f}" if b_hi < 1e9 else f"{b_lo:.0f}+"
            lines.append(f"  - {label} m² : {c}")
    capped = (last_page_with_data < max_pages - 1
              and isinstance(total, int) and total > fetched + PAGE_SIZE)
    lines.append(
        "- verdict : " + (
            "pagination PLAFONNÉE (la collecte s'arrête avant le total) -> "
            "balayage par tranches de surface requis"
            if capped else
            "pagination semble se poursuivre -> lever MAX_PAGES suffirait "
            "(ou épuisement réel atteint)"
        )
    )
    return "\n".join(lines) + "\n"


def field_audit_md(city: str = CITY, max_pages: int = 4) -> str:
    """Audit B0 : quels champs l'API bien'ici expose réellement, avec leur taux
    de remplissage, et focus DPE + année de construction (noms exacts +
    échantillons de valeurs). Sert à calibrer l'usage des critères (filtre dur
    si bien rempli, sinon signal explicatif)."""
    zone_ids = discover_zone_ids(city)
    if not zone_ids:
        return f"## Audit champs bienici ({city})\n\n_(pas de zoneId)_\n"

    ads = []
    for page in range(max_pages):
        data = fetch_json(ADS_URL, params=_build_filters(zone_ids, page))
        if not isinstance(data, dict):
            break
        page_ads = data.get("realEstateAds", [])
        if not page_ads:
            break
        ads.extend(page_ads)
        if len(page_ads) < 50:
            break

    n = len(ads)
    if not n:
        return f"## Audit champs bienici ({city})\n\n_(aucune annonce)_\n"

    fill = Counter()
    for a in ads:
        for k, v in a.items():
            if v not in (None, "", [], {}):
                fill[k] += 1

    def _kw(*words):
        return [k for k in fill if any(w in k.lower() for w in words)]

    energy_keys = _kw("energy", "dpe", "ges", "greenhouse", "energie")
    year_keys = _kw("year", "construction", "built", "annee")
    # Prérequis #0 incrément 2 : le pivot du matching photo exige des URLs photo
    # dans le JSON ; le wording « publié chez X » exige un nom d'agence/contact.
    photo_keys = _kw("photo", "image", "picture", "media", "thumbnail", "visual")
    agency_keys = _kw("agency", "agence", "contact", "professional", "advertiser",
                      "account", "publisher", "vendor")

    def _samples(keys):
        out = []
        for k in keys:
            vals = []
            for a in ads:
                v = a.get(k)
                if v not in (None, "", [], {}) and v not in vals:
                    vals.append(v)
                if len(vals) >= 4:
                    break
            out.append(f"  - `{k}` ({fill[k]}/{n}) ex: {vals}")
        return out

    def _preview(v, maxlen: int = 160) -> str:
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
        return s[:maxlen] + ("…" if len(s) > maxlen else "")

    def _media_samples(keys):
        """Échantillon compact (les tableaux de photos sont volumineux) : pour
        chaque clé, taux de remplissage + 1er exemple non vide tronqué, et la
        taille si c'est une liste (nombre de photos)."""
        out = []
        for k in keys:
            sample = None
            for a in ads:
                v = a.get(k)
                if v not in (None, "", [], {}):
                    sample = v
                    break
            extra = f" [liste de {len(sample)}]" if isinstance(sample, list) else ""
            out.append(f"  - `{k}` ({fill[k]}/{n}){extra} ex: {_preview(sample)}")
        return out

    lines = [f"## Audit champs bienici ({city}) — {n} annonces"]
    lines.append("### Photos / médias (faisabilité matching incrément 2)")
    lines += _media_samples(photo_keys) or ["  - AUCUN champ photo/image/media — "
                                            "pivot du matching photo COMPROMIS"]
    lines.append("### Agence / contact (wording « publié chez X »)")
    lines += _media_samples(agency_keys) or ["  - aucun champ agence/contact exposé"]
    lines.append("### DPE / énergie")
    lines += _samples(energy_keys) or ["  - aucun champ"]
    lines.append("### Année de construction")
    lines += _samples(year_keys) or ["  - aucun champ"]
    lines.append("### Tous les champs (remplissage)")
    for k, c in fill.most_common():
        lines.append(f"  - `{k}` : {c}/{n}")
    return "\n".join(lines) + "\n"


def main() -> None:
    zone_ids = step1_zone()
    step2_raw(zone_ids)
    step3_scrape()
    step4_low_tail(zone_ids)
    print("\n" + "=" * 70)
    print(field_audit_md())
    print("\n" + "=" * 70)
    print("Succès attendu : total bas, dépt 57, prix/m² réalistes (~2000-3500).")


if __name__ == "__main__":
    main()
