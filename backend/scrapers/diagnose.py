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
    for name in names:
        logger.info("Diagnostic de la source '%s'...", name)
        try:
            listings = _registry[name]().scrape()
        except Exception as e:
            logger.exception("Scraper '%s' a levé une exception.", name)
            blocks.append(f"### `{name}` — FAIL (exception)\n- `{type(e).__name__}: {e}`\n")
            any_fail = True
            continue
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

    return report, any_fail


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
