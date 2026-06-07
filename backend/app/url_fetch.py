import json
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse
import logging

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger("url_fetch")
logger.setLevel(logging.INFO)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

TIMEOUT = 10
MAX_TEXT_LENGTH = 8000
MIN_TEXT_LENGTH = 80


def _is_safe_url(url: str) -> bool:
    """Filtre minimal anti-SSRF : http/https publics uniquement."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    blocked_exact = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
    blocked_prefixes = ("10.", "192.168.", "169.254.", "172.16.", "172.17.",
                        "172.18.", "172.19.", "172.20.", "172.21.", "172.22.",
                        "172.23.", "172.24.", "172.25.", "172.26.", "172.27.",
                        "172.28.", "172.29.", "172.30.", "172.31.")
    if host in blocked_exact or host.startswith(blocked_prefixes):
        return False
    return True


def _extract_text_from_html(html: str, url: str) -> Optional[str]:
    """Extrait le contenu textuel principal d'un HTML brut (comportement
    historique de fetch_listing_text : container principal, plafond, seuil min)."""
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        logger.warning("HTML parse failed for %s: %s", url, e)
        return None

    for tag in soup(["script", "style", "noscript", "nav", "header",
                     "footer", "iframe", "svg", "form", "button"]):
        tag.decompose()

    container = soup.find("main") or soup.find("article") or soup.body or soup
    text = container.get_text(separator=" ", strip=True)
    text = " ".join(text.split())

    if len(text) < MIN_TEXT_LENGTH:
        logger.warning("Extracted text too short for %s (len=%d)", url, len(text))
        return None

    logger.info("Extracted %d chars from %s", len(text), url)
    return text[:MAX_TEXT_LENGTH]


def fetch_listing(url: str) -> Optional[Dict[str, Optional[str]]]:
    """Télécharge la page UNE SEULE FOIS et renvoie son texte extrait + le HTML
    brut. `{"text": <texte tronqué|None>, "html": <html brut>}`, ou None si la
    requête échoue ou si l'URL n'est pas sûre.

    Le HTML brut est exposé pour permettre l'extraction d'images (JSON-LD dans
    les <script>, décomposés par le nettoyage texte) sans doubler le GET réseau.
    """
    if not _is_safe_url(url):
        logger.warning("URL rejected (unsafe): %s", url)
        return None

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        logger.info("Fetched %s -> status=%s, bytes=%d, ct=%s",
                    url, resp.status_code, len(resp.text or ""),
                    resp.headers.get("content-type", ""))
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("URL fetch failed for %s: %s", url, e)
        return None

    html = resp.text or ""
    return {"text": _extract_text_from_html(html, url), "html": html}


def fetch_listing_text(url: str) -> Optional[str]:
    """Télécharge la page et extrait son contenu textuel principal.

    Retourne None si la requête échoue, si le contenu est vide,
    ou si l'URL n'est pas sûre.
    """
    result = fetch_listing(url)
    if result is None:
        return None
    return result["text"]


def _jsonld_images(data: Any, out: list) -> None:
    """Collecte récursivement les valeurs de clé `image` d'un objet JSON-LD
    (chaîne, liste de chaînes, ou objet ImageObject avec `url`)."""
    if isinstance(data, dict):
        img = data.get("image")
        if isinstance(img, str):
            out.append(img)
        elif isinstance(img, list):
            for it in img:
                if isinstance(it, str):
                    out.append(it)
                elif isinstance(it, dict) and isinstance(it.get("url"), str):
                    out.append(it["url"])
        elif isinstance(img, dict) and isinstance(img.get("url"), str):
            out.append(img["url"])
        for value in data.values():
            _jsonld_images(value, out)
    elif isinstance(data, list):
        for item in data:
            _jsonld_images(item, out)


def extract_image_urls(html: str, base_url: str) -> list:
    """Extrait les URLs d'images d'une page d'annonce, par ordre de priorité :
    meta og:image / twitter:image, puis JSON-LD `image`, puis <img> de galerie
    (src, à défaut data-src). Les URLs relatives sont résolues via urljoin et la
    liste est dédupliquée en préservant l'ordre. Ne lève jamais (HTML malformé
    ou absence de balise -> liste éventuellement vide).

    Opère sur le HTML BRUT : le JSON-LD vit dans <script type="application/ld+json">,
    décomposé par le nettoyage texte ; on doit donc lire avant toute décomposition.
    """
    candidates: list = []
    try:
        soup = BeautifulSoup(html or "", "html.parser")

        for meta in soup.find_all("meta"):
            prop = (meta.get("property") or meta.get("name") or "").lower()
            if prop in ("og:image", "twitter:image"):
                content = meta.get("content")
                if isinstance(content, str) and content.strip():
                    candidates.append(content.strip())

        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text() or ""
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue
            _jsonld_images(data, candidates)

        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if isinstance(src, str) and src.strip():
                candidates.append(src.strip())
    except Exception as e:
        logger.warning("image extraction failed: %s", e)
        return []

    seen: set = set()
    urls: list = []
    for src in candidates:
        try:
            resolved = urljoin(base_url, src)
        except Exception:
            continue
        if resolved and resolved not in seen:
            seen.add(resolved)
            urls.append(resolved)
    return urls
