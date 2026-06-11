"""
Harnais de diagnostic des scrapers — coeur de la boucle d'automatisation.

Le sandbox de développement n'a aucun accès réseau sortant : le seul endroit
où un scraper touche réellement Internet est un runner GitHub Actions. Ce
module produit un rapport Markdown lisible (le canal de retour fiable étant
un commentaire de PR, pas les logs bruts d'Actions).

Usage (depuis backend/) :
    python -m scrapers.diagnose                 # diagnostique toutes les sources
    python -m scrapers.diagnose --source orpi   # une seule source enregistrée
    python -m scrapers.diagnose --recon <url>   # auscultation HTML brute d'une URL
    python -m scrapers.diagnose --out report.md # chemin du rapport (déf. diag_report.md)

Le rapport est écrit dans --out ET affiché sur stdout. Code de sortie non nul
si au moins une source renvoie zéro annonce (utile comme garde-fou CI).

Aucune écriture en base.
"""

import argparse
import logging
import sys
from collections import Counter
from statistics import median
from typing import Optional

from scrapers.models import PropertyListing
from scrapers.registry import _registry
from scrapers.sources import load_all

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scrapers.diagnose")

# Bande de plausibilité prix/m² pour une vente résidentielle messine
# (même filet que le scraper Bien'ici). Hors bande = loyer, parking,
# viager ou erreur de saisie.
MIN_PRICE_M2 = 800.0
MAX_PRICE_M2 = 12000.0

# Seuil en deçà duquel une source est jugée fragile (signal, pas blocage).
HEALTHY_MIN = 5


def _price_m2(listing: PropertyListing) -> Optional[float]:
    if listing.surface_m2 and listing.surface_m2 > 0:
        return listing.price_total / listing.surface_m2
    return None


def build_source_report(name: str, listings: list[PropertyListing]) -> tuple[str, str]:
    """Retourne (status, markdown) pour une source. status ∈ {ok, warn, fail}."""
    count = len(listings)
    if count == 0:
        md = (
            f"### `{name}` — FAIL (0 annonce)\n"
            "- Le scraper n'a renvoyé aucune annonce exploitable.\n"
            "- Pistes : URL de listing erronée, sélecteur de carte cassé, "
            "ou page rendue côté JS.\n"
            f"- Auscultez le HTML brut : `python -m scrapers.diagnose --recon <url>`\n"
        )
        return "fail", md

    by_city = Counter(l.city for l in listings)
    by_type = Counter(l.property_type for l in listings)
    prices = sorted(p for l in listings if (p := _price_m2(l)) is not None)
    out_of_band = sum(1 for p in prices if p < MIN_PRICE_M2 or p > MAX_PRICE_M2)
    no_district = sum(1 for l in listings if not l.district)

    band_ratio = out_of_band / count if count else 0
    status = "ok"
    if count < HEALTHY_MIN or band_ratio > 0.1:
        status = "warn"
    label = {"ok": "OK", "warn": "WARN"}[status]

    lines = [f"### `{name}` — {label} ({count} annonces)"]
    lines.append(f"- villes : {dict(by_city.most_common(8))}")
    lines.append(f"- types : {dict(by_type)}")
    if prices:
        lines.append(
            f"- prix/m² : min={prices[0]:.0f} médiane={median(prices):.0f} "
            f"max={prices[-1]:.0f} €/m²"
        )
    lines.append(
        f"- hors bande [{MIN_PRICE_M2:.0f}-{MAX_PRICE_M2:.0f}] : {out_of_band} "
        f"({band_ratio:.0%})"
    )
    lines.append(f"- sans district : {no_district}/{count}")
    districts = Counter(l.district for l in listings if l.district)
    if districts:
        lines.append(f"- quartiers distincts ({len(districts)}) : {dict(districts.most_common(12))}")
    with_dpe = sum(1 for l in listings if getattr(l, "dpe", None))
    with_year = sum(1 for l in listings if getattr(l, "construction_year", None))
    with_postal = sum(1 for l in listings if getattr(l, "postal_code", None))
    lines.append(f"- avec DPE : {with_dpe}/{count} · avec année constr. : {with_year}/{count}")
    lines.append(f"- avec code postal : {with_postal}/{count}")
    with_floor = sum(1 for l in listings if getattr(l, "floor", None) is not None)
    with_elev = sum(1 for l in listings if getattr(l, "has_elevator", None) is not None)
    with_terr = sum(1 for l in listings if getattr(l, "has_terrace", None) is not None)
    lines.append(f"- avec étage : {with_floor}/{count} · ascenseur : {with_elev}/{count} · terrasse : {with_terr}/{count}")
    lines.append("- échantillon :")
    for l in listings[:5]:
        pm2 = _price_m2(l) or 0
        lines.append(
            f"  - `[{l.property_type}]` {l.city} — {l.surface_m2:.0f} m² — "
            f"{l.price_total:.0f} € ({pm2:.0f} €/m²) — district={l.district}"
        )
    return status, "\n".join(lines) + "\n"


def diagnose_sources(only: Optional[str] = None) -> tuple[str, bool]:
    """Exécute les scrapers enregistrés. Retourne (markdown, any_fail)."""
    load_all()
    names = [only] if only else sorted(_registry)
    if only and only not in _registry:
        return (
            f"## Diagnostic scrapers\n\nSource `{only}` inconnue. "
            f"Sources enregistrées : {sorted(_registry)}\n",
            True,
        )

    blocks, any_fail = [], False
    scraped: dict[str, list] = {}
    for name in names:
        logger.info("Diagnostic de la source '%s'...", name)
        try:
            listings = _registry[name]().scrape()
        except Exception as e:
            logger.exception("Scraper '%s' a levé une exception.", name)
            blocks.append(f"### `{name}` — FAIL (exception)\n- `{type(e).__name__}: {e}`\n")
            any_fail = True
            continue
        scraped[name] = listings
        status, block = build_source_report(name, listings)
        any_fail = any_fail or status == "fail"
        blocks.append(block)

    header = f"## Diagnostic scrapers ({len(names)} source(s))\n\n"
    report = header + "\n".join(blocks)

    # Section dédiée : queue basse bienici (champs discriminants) pour traquer
    # ce qui tire la médiane Metz vers le bas.
    if "bienici" in names:
        try:
            from scrapers.diag_bienici import low_price_tail_md, field_audit_md
            report += "\n\n---\n\n" + low_price_tail_md()
            report += "\n\n---\n\n" + field_audit_md()
        except Exception as e:
            logger.warning("diagnostic bienici étendu a échoué : %s", e)
        try:
            from scrapers.diag_bienici import dedup_signals_md
            report += "\n\n---\n\n" + dedup_signals_md()
        except Exception as e:
            logger.warning("probe dédup exacte bienici a échoué : %s", e)
        try:
            report += "\n\n---\n\n" + sector_depth_md(scraped.get("bienici", []))
        except Exception as e:
            logger.warning("mesure profondeur secteur a échoué : %s", e)

    # Probe « gisement » cross-agence (prérequis #0 incrément 2) : n'a de sens
    # qu'avec plusieurs sources scrapées (recouvrement INTER-sources).
    if len(scraped) >= 2:
        try:
            report += "\n\n---\n\n" + cross_source_overlap_md(scraped)
        except Exception as e:
            logger.warning("probe recouvrement cross-source a échoué : %s", e)

    return report, any_fail


def sector_depth_md(listings: list, surface: float = 70.0,
                    prop_type: str = "appartement") -> str:
    """Profondeur de la cascade pour un bien représentatif : combien de
    comparables chaque quartier / secteur réunit dans la fenêtre type+surface
    (±20%), face au seuil d'affinage. Révèle pourquoi l'analyse retombe (ou non)
    au niveau ville. Mesure sur les annonces scrapées (≈ contenu de la base)."""
    from collections import Counter
    from app.market_stats import _SECTOR_DISTRICTS, MIN_REFINED_COMPARABLES

    lo, hi = surface * 0.8, surface * 1.2
    in_win = [l for l in listings
              if l.property_type == prop_type and l.surface_m2 and lo <= l.surface_m2 <= hi]
    by_q = Counter(l.district for l in in_win if l.district)

    def flag(c: int) -> str:
        return "OK" if c >= MIN_REFINED_COMPARABLES else "< seuil"

    flats = [l for l in listings if l.property_type == prop_type and l.surface_m2]

    lines = [
        f"## Profondeur quartier/secteur (bienici) — {prop_type} {surface:.0f} m²",
        f"- fenêtre surface ±20% : {lo:.0f}–{hi:.0f} m² · seuil d'affinage : "
        f"{MIN_REFINED_COMPARABLES}",
        f"- {len(in_win)} biens dans la fenêtre (sur {len(flats)} {prop_type}s)",
    ]

    # Histogramme des surfaces : la fenêtre ±20% est-elle juste trop étroite,
    # ou la base manque-t-elle vraiment de profondeur ?
    buckets = [(0, 40), (40, 55), (55, 70), (70, 85), (85, 100), (100, 1e9)]
    lines.append("### Histogramme surfaces (appartements)")
    for b_lo, b_hi in buckets:
        c = sum(1 for l in flats if b_lo <= l.surface_m2 < b_hi)
        label = f"{b_lo:.0f}-{b_hi:.0f} m²" if b_hi < 1e9 else f"{b_lo:.0f}+ m²"
        lines.append(f"  - {label} : {c}")

    # Sensibilité de la fenêtre : combien la ville et le meilleur secteur
    # réuniraient à ±20 / 30 / 40 %.
    lines.append("### Sensibilité fenêtre (ville / meilleur secteur)")
    for pct in (0.2, 0.3, 0.4):
        wlo, whi = surface * (1 - pct), surface * (1 + pct)
        win = [l for l in flats if wlo <= l.surface_m2 <= whi]
        bq = Counter(l.district for l in win if l.district)
        best = max(
            ((sec, sum(bq.get(d, 0) for d in dists)) for sec, dists in _SECTOR_DISTRICTS.items()),
            key=lambda kv: kv[1], default=("-", 0),
        )
        lines.append(
            f"  - ±{pct*100:.0f}% ({wlo:.0f}-{whi:.0f}) : ville={len(win)} · "
            f"meilleur secteur={best[0]} {best[1]}"
        )

    lines.append("### Par quartier (fenêtre ±20%)")
    for q, c in by_q.most_common():
        lines.append(f"  - {q} : {c} [{flag(c)}]")
    lines.append("### Par secteur (somme des quartiers, fenêtre ±20%)")
    for sec, dists in _SECTOR_DISTRICTS.items():
        c = sum(by_q.get(d, 0) for d in dists)
        lines.append(f"  - {sec} : {c} [{flag(c)}]  ({', '.join(dists)})")
    return "\n".join(lines) + "\n"


def _representative_card_html(soup, max_len: int = 3500) -> Optional[str]:
    """HTML d'une carte d'annonce plausible : plus petit élément contenant à la
    fois un prix (€), une surface (m²) et un lien. Révèle la vraie structure
    (classes réelles, href de détail, emplacement des champs) pour écrire les
    sélecteurs sans accès réseau."""
    import re

    candidates = []
    for el in soup.find_all(True):
        text = el.get_text(" ", strip=True)
        if "€" not in text or not re.search(r"\d+\s*m[²2]", text, re.I):
            continue
        if not el.find("a", href=True):
            continue
        length = len(text)
        if 30 <= length <= 600:
            candidates.append((length, el))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    html = candidates[0][1].prettify()
    return html[:max_len] + ("\n... (tronqué)" if len(html) > max_len else "")


def run_recon(url: str) -> str:
    """Auscultation HTML brute d'une URL (statut, signaux prix, sélecteurs)."""
    # Import paresseux : recon dépend de bs4, absent du sandbox de dev.
    import time

    import requests

    from scrapers.recon import (
        HEADERS,
        TIMEOUT,
        check_robots,
        detect_price_surface,
        suggest_card_selectors,
    )
    from bs4 import BeautifulSoup

    lines = [f"## Recon — {url}\n", f"- robots.txt : {check_robots(url)}"]
    t0 = time.time()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as e:
        lines.append(f"- ERREUR RESEAU : `{e}`")
        return "\n".join(lines) + "\n"

    html = resp.text or ""
    lines.append(
        f"- HTTP {resp.status_code} — {len(html)} octets — {time.time() - t0:.1f}s"
    )
    if resp.status_code != 200:
        lines.append(f"- VERDICT : statut {resp.status_code} (anti-bot probable si 403/429)")
        return "\n".join(lines) + "\n"

    prices, surfaces = detect_price_surface(html)
    lines.append(f"- signaux HTML : {prices} prix (€), {surfaces} surfaces (m²)")
    if prices >= 3:
        soup = BeautifulSoup(html, "html.parser")
        lines.append("- VERDICT : FAISABLE (contenu en HTML serveur)")
        lines.append("- classes CSS candidates (éléments contenant €) :")
        for cls, n in suggest_card_selectors(soup):
            lines.append(f"  - `.{cls}` (x{n})")
        sample = _representative_card_html(soup)
        if sample:
            lines.append("- structure d'une carte représentative :")
            lines.append("```html\n" + sample + "\n```")
    elif len(html) > 20000:
        lines.append("- VERDICT : PROBABLEMENT JS-ONLY (page lourde, pas de prix en HTML)")
    else:
        lines.append("- VERDICT : INCERTAIN (peu de contenu — vérifier l'URL de listing)")
    return "\n".join(lines) + "\n"


def run_recon_all() -> str:
    """Ausculte toutes les agences candidates listées dans recon.SITES."""
    from scrapers.recon import SITES

    blocks = ["## Recon des agences candidates\n"]
    for name, url in SITES.items():
        blocks.append(f"### {name}\n" + run_recon(url))
    return "\n".join(blocks)


def cross_source_overlap_md(scraped: dict[str, list]) -> str:
    """Probe « gisement » cross-agence — prérequis #0 de l'incrément 2 (§9.1).

    Mesure, SUR LES ANNONCES FRAÎCHEMENT SCRAPÉES (≈ contenu de la base, le
    sandbox n'ayant pas d'egress), le recouvrement réel ENTRE sources — borne
    basse du multi-mandat visible chez nous, AVANT d'investir dans le pipeline
    image :
      - paires candidates INTER-sources strictes (§9.1 : même type, même ville,
        code postal compatible, surface ±2 %, prix ±2 %) ;
      - paires candidates INTER-sources larges (§5.2 : même type, même ville,
        surface ±10 %, prix libre) — borne haute des cas que le matcher photo
        aurait à arbitrer ;
      - doublons INTRA-bienici (republications : même type/quartier/surface
        arrondie) — indice de doublons à l'intérieur du portail pivot.

    Aucun accès réseau au-delà du scrape déjà fait, aucune écriture en base.
    """
    from collections import defaultdict

    all_listings = [l for ls in scraped.values() for l in ls]
    n = len(all_listings)
    by_source = Counter(l.source for l in all_listings)
    if n == 0 or len(scraped) < 2:
        return ("## Recouvrement inter-sources (prérequis #0 incrément 2)\n\n"
                "_(probe ignorée : moins de 2 sources scrapées)_\n")

    def _surf_ok(a, b, tol: float) -> bool:
        sa, sb = a.surface_m2, b.surface_m2
        return bool(sa and sb) and abs(sa - sb) <= tol * max(sa, sb)

    def _price_ok(a, b, tol: float) -> bool:
        pa, pb = a.price_total, b.price_total
        return bool(pa and pb) and abs(pa - pb) <= tol * max(pa, pb)

    def _postal_compatible(a, b) -> bool:
        # Si les DEUX ont un code postal, ils doivent coïncider ; sinon la ville
        # canonique fait déjà foi (on n'exclut pas).
        if a.postal_code and b.postal_code:
            return a.postal_code == b.postal_code
        return True

    # On ne compare que des biens plausiblement comparables : même (type, ville).
    # Balayage trié par surface avec fenêtre glissante (évite le O(n²) global).
    groups: dict = defaultdict(list)
    for l in all_listings:
        if l.surface_m2 and l.price_total and l.city and l.property_type:
            groups[(l.property_type, l.city)].append(l)

    strict_pairs = 0
    loose_pairs = 0
    cross_ids: set = set()       # ids ayant >=1 candidat inter-source (large)
    agency_bienici_pairs = 0     # paires agence <-> bienici (large)
    examples: list = []

    for group in groups.values():
        group.sort(key=lambda x: x.surface_m2)
        m = len(group)
        for i in range(m):
            a = group[i]
            for j in range(i + 1, m):
                b = group[j]
                # Fenêtre : marge un peu au-delà de +10 % pour ne rien manquer
                # à la borne (le test exact est fait par _surf_ok).
                if b.surface_m2 > a.surface_m2 * 1.12:
                    break
                if a.source == b.source or not _postal_compatible(a, b):
                    continue
                if not _surf_ok(a, b, 0.10):
                    continue
                loose_pairs += 1
                cross_ids.add(a.id)
                cross_ids.add(b.id)
                if "bienici" in (a.source, b.source):
                    agency_bienici_pairs += 1
                if _surf_ok(a, b, 0.02) and _price_ok(a, b, 0.02):
                    strict_pairs += 1
                    if len(examples) < 8:
                        examples.append((a, b))

    pct_cross = len(cross_ids) / n * 100.0
    agency_n = n - by_source.get("bienici", 0)
    # Recouvrement STRICT rapporté au parc agences (hors bienici) : combien de
    # mandats d'agence ont un quasi-jumeau (surface ET prix ±2 %) ailleurs. C'est
    # le signal honnête ; la métrique « large » est une borne haute BRUITÉE
    # (similarité d'attributs sur le même segment, PAS identité d'un bien).
    pct_strict_vs_agency = (strict_pairs / agency_n * 100.0) if agency_n else 0.0

    # Doublons intra-bienici (republications) : même (type, quartier, surface arrondie).
    bienici = scraped.get("bienici", [])
    buckets: dict = defaultdict(int)
    for l in bienici:
        if l.surface_m2 and l.district and l.property_type:
            buckets[(l.property_type, l.district, round(l.surface_m2))] += 1
    intra_dup_groups = sum(1 for c in buckets.values() if c > 1)
    intra_dup_listings = sum(c for c in buckets.values() if c > 1)

    # Verdict basé sur la métrique STRICTE (la large est du bruit). Seuil indicatif :
    # si quasi aucune paire stricte, le gisement attribut est trop ténu pour
    # justifier le pipeline image ; sinon il existe mais reste à départager du
    # simple « même segment » par les photos.
    verdict = (
        "gisement attribut TÉNU (quasi aucune paire stricte) -> repli incrément 1 "
        "seul à considérer (à recouper avec la faisabilité photos)"
        if strict_pairs < 10 else
        "gisement attribut RÉEL mais à départager (attributs proches != même bien) "
        "-> le matching photo est précisément le discriminant ; décision "
        "conditionnée à la faisabilité photos (Partie B / diag-bienici)"
    )

    lines = [
        "## Recouvrement inter-sources (prérequis #0 incrément 2)",
        f"- annonces scrapées : {n} · par source : {dict(by_source.most_common())}",
        f"- parc agences hors bienici : {agency_n}",
        f"- paires candidates INTER-sources **strictes** (±2 % surface ET ±2 % prix) : "
        f"**{strict_pairs}** (= {pct_strict_vs_agency:.1f} % du parc agences)",
        f"- paires candidates INTER-sources LARGES (±10 % surface, prix libre) : "
        f"{loose_pairs} (dont {agency_bienici_pairs} impliquant bienici) "
        f"— **borne haute BRUITÉE** (similarité d'attributs, PAS identité)",
        f"- annonces avec ≥1 candidat large : {len(cross_ids)}/{n} = {pct_cross:.1f} % "
        f"(non significatif : mesure la densité du segment, pas le multi-mandat)",
        f"- doublons INTRA-bienici (même type/quartier/surface±0.5 m²) : "
        f"{intra_dup_listings} annonces dans {intra_dup_groups} grappes — coarse, "
        f"surévalue (attributs seuls ne distinguent pas deux biens du même segment)",
        f"- **verdict gisement** : {verdict}",
    ]
    if examples:
        lines.append("- exemples de paires strictes :")
        for a, b in examples:
            lines.append(
                f"  - {a.source}↔{b.source} | {a.property_type} {a.city} | "
                f"{a.surface_m2:.0f}/{b.surface_m2:.0f} m² | "
                f"{a.price_total:.0f}/{b.price_total:.0f} € | "
                f"cp {a.postal_code}/{b.postal_code} · quartier {a.district}/{b.district}"
            )
    lines.append(
        "- NB : borne BASSE (un même bien chez deux agences n'a pas toujours des "
        "attributs identiques ; le matching photo en récupérerait davantage). "
        "Une probe attributs ne PROUVE pas le « même bien » — elle borne le gisement."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostic des scrapers")
    parser.add_argument("--source", help="Nom d'une source enregistrée à diagnostiquer")
    parser.add_argument("--recon", help="URL à ausculter (HTML brut, pas de base)")
    parser.add_argument("--recon-all", action="store_true",
                        help="Ausculte toutes les agences candidates (recon.SITES)")
    parser.add_argument("--out", default="diag_report.md", help="Fichier rapport Markdown")
    args = parser.parse_args()

    if args.recon:
        report, any_fail = run_recon(args.recon), False
    elif args.recon_all:
        report, any_fail = run_recon_all(), False
    else:
        report, any_fail = diagnose_sources(args.source)

    try:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
    except OSError as e:
        logger.warning("Impossible d'écrire %s : %s", args.out, e)

    print(report)
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
