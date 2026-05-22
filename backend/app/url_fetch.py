from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


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


def fetch_listing_text(url: str) -> Optional[str]:
    """Télécharge la page et extrait son contenu textuel principal.

    Retourne None si la requête échoue, si le contenu est vide,
    ou si l'URL n'est pas sûre.
    """
    if not _is_safe_url(url):
        return None

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return None

    for tag in soup(["script", "style", "noscript", "nav", "header",
                     "footer", "iframe", "svg", "form", "button"]):
        tag.decompose()

    container = soup.find("main") or soup.find("article") or soup.body or soup
    text = container.get_text(separator=" ", strip=True)
    text = " ".join(text.split())

    if len(text) < MIN_TEXT_LENGTH:
        return None

    return text[:MAX_TEXT_LENGTH]
