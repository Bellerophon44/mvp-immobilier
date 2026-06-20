"""
Script de reconnaissance des sites d'agences (Bloc 1).

Usage (depuis backend/, ou n'importe où) :
    python scrapers/recon.py
    python scrapers/recon.py https://un-site.fr/une-page-listing   # tester une URL précise

Le script, pour chaque site :
  - lit le robots.txt et indique si la page est autorisée
  - télécharge la page de listing avec un User-Agent navigateur
  - mesure statut HTTP, taille, temps de réponse
  - détecte si les prix/surfaces sont présents dans le HTML (sinon = JS-only)
  - propose des classes CSS candidates pour repérer les "cartes" d'annonces
  - sauvegarde le HTML brut dans recon_dumps/<site>.html pour analyse

Aucune écriture en base. Aucune dépendance autre que requests + beautifulsoup4.
"""

import os
import re
import sys
import time
import urllib.robotparser
from collections import Counter
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    sys.exit("Manque 'requests' : pip install requests")

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Manque 'beautifulsoup4' : pip install beautifulsoup4")


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
TIMEOUT = 20

# URLs de listing des agences candidates (cibles du recon en CI).
# laveine.immo, idemmo et benedic sont deja des sources actives, donc absentes.
# Ecartees apres recon : herbeth, agencevalentin (robots interdit + 403),
# century21 et orpi (rendu JS-only, pas de prix dans le HTML serveur).
#
# Vague couronne (incrément 3, GATE 1 « recon avant code ») : recon effectue le
# 2026-06-20 sur 3 candidates locales independantes -> 0 retenue (Les Artisans de
# l'Immobilier : HTML serveur propre + maisons couronne mais robots.txt interdit ;
# SOREC : JS-only). Verdicts archives dans
# docs/specs/increment3-couronne-RESULTATS-RECON.md. SITES remis a vide : le recon
# tourne en CI (egress local sur allowlist) ; ajouter une URL ici pour ausculter
# une nouvelle agence au prochain run (rendu serveur presume, .htm/.html/.php).
SITES: dict[str, str] = {}

DUMP_DIR = "recon_dumps"

CARD_HINT_WORDS = (
    "annonce", "bien", "property", "propert", "card", "product",
    "result", "listing", "item", "offre", "estate", "teaser", "vignette",
)


def check_robots(url: str) -> str:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as e:
        return f"robots.txt illisible ({e})"
    allowed = rp.can_fetch(USER_AGENT, url)
    return "autorisé" if allowed else "INTERDIT par robots.txt"


def detect_price_surface(html: str) -> tuple:
    prices = len(re.findall(r"\d[\d  \.]*\s*€", html))
    surfaces = len(re.findall(r"\d+\s*m[²2]", html, flags=re.IGNORECASE))
    return prices, surfaces


def suggest_card_selectors(soup: BeautifulSoup) -> list:
    """Cherche les classes CSS portées par des éléments contenant un prix."""
    counter = Counter()
    for el in soup.find_all(True):
        text = el.get_text(" ", strip=True)
        if "€" not in text:
            continue
        if len(text) > 600:  # trop gros : conteneur global, pas une carte
            continue
        classes = el.get("class") or []
        for c in classes:
            counter[c] += 1
    # Priorise les classes dont le nom évoque une carte d'annonce
    scored = []
    for cls, n in counter.items():
        bonus = 5 if any(w in cls.lower() for w in CARD_HINT_WORDS) else 0
        scored.append((n + bonus, n, cls))
    scored.sort(reverse=True)
    return [(cls, n) for _, n, cls in scored[:12]]


def recon_one(name: str, url: str) -> None:
    print("\n" + "=" * 70)
    print(f"SITE : {name}")
    print(f"URL  : {url}")
    print("-" * 70)

    print(f"robots.txt : {check_robots(url)}")

    t0 = time.time()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"VERDICT    : ERREUR RESEAU ({e})")
        return
    elapsed = time.time() - t0

    html = resp.text or ""
    ctype = resp.headers.get("content-type", "")
    print(f"HTTP       : {resp.status_code} | {len(html)} octets | "
          f"{ctype} | {elapsed:.1f}s")

    if resp.status_code in (403, 401, 429):
        print(f"VERDICT    : BLOQUE (status {resp.status_code}) — anti-bot probable")
        _dump(name, html)
        return
    if resp.status_code != 200:
        print(f"VERDICT    : status inattendu {resp.status_code}")
        _dump(name, html)
        return

    prices, surfaces = detect_price_surface(html)
    print(f"Signaux    : {prices} prix (€) | {surfaces} surfaces (m²) dans le HTML brut")

    soup = BeautifulSoup(html, "html.parser")

    if prices >= 3:
        print("VERDICT    : FAISABLE — contenu présent en HTML serveur")
        print("Classes CSS candidates pour les cartes d'annonces :")
        for cls, n in suggest_card_selectors(soup):
            print(f"             .{cls}  (x{n})")
    elif len(html) > 20000:
        print("VERDICT    : PROBABLEMENT JS-ONLY — page lourde mais sans prix "
              "en HTML (rendu côté navigateur). Nécessitera Playwright.")
    else:
        print("VERDICT    : INCERTAIN — peu de contenu, vérifier l'URL de listing")

    _dump(name, html)


def _dump(name: str, html: str) -> None:
    os.makedirs(DUMP_DIR, exist_ok=True)
    path = os.path.join(DUMP_DIR, f"{name}.html")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML sauvé : {path}")
    except OSError as e:
        print(f"(impossible de sauver le HTML : {e})")


def main() -> None:
    args = sys.argv[1:]
    if args:
        for i, url in enumerate(args):
            recon_one(f"cli_{i}", url)
    else:
        for name, url in SITES.items():
            recon_one(name, url)
    print("\n" + "=" * 70)
    print("Reco terminée. Envoie la sortie console + le contenu de "
          f"'{DUMP_DIR}/' (ou zippe-le) pour l'écriture des scrapers.")


if __name__ == "__main__":
    main()
