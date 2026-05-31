import time
import random
import hashlib
import logging
import re
import unicodedata
from typing import Any, Optional

import requests


logger = logging.getLogger("scrapers.base")
logger.setLevel(logging.INFO)


# -------------------------
# Configuration HTTP
# -------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

REQUEST_TIMEOUT = 15           # secondes
DEFAULT_DELAY = 1.5            # délai poli moyen entre deux requêtes (s)
MAX_RETRIES = 3
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

_session = requests.Session()
_session.headers.update(HEADERS)


def polite_sleep(base_delay: float = DEFAULT_DELAY) -> None:
    """Pause aléatoire autour de base_delay pour ne pas marteler un site."""
    jitter = random.uniform(-0.4, 0.6)
    time.sleep(max(0.3, base_delay + jitter))


# -------------------------
# Téléchargement de page
# -------------------------

def fetch_page(
    url: str,
    delay: float = DEFAULT_DELAY,
    max_retries: int = MAX_RETRIES,
) -> Optional[str]:
    """
    Télécharge une page HTML avec retries et backoff.

    Retourne le HTML, ou None si la page reste inaccessible.
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = _session.get(url, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            logger.warning("fetch_page error (%d/%d) %s: %s",
                           attempt, max_retries, url, e)
            polite_sleep(delay * attempt)
            continue

        if resp.status_code in RETRYABLE_STATUS:
            logger.warning("fetch_page status %d (%d/%d) %s",
                           resp.status_code, attempt, max_retries, url)
            polite_sleep(delay * attempt)
            continue

        if resp.status_code != 200:
            logger.warning("fetch_page status %d (non-retryable) %s",
                           resp.status_code, url)
            return None

        logger.info("fetch_page OK %s (bytes=%d)", url, len(resp.text or ""))
        return resp.text

    logger.warning("fetch_page gave up after %d attempts: %s", max_retries, url)
    return None


def fetch_json(
    url: str,
    params: Optional[dict] = None,
    delay: float = DEFAULT_DELAY,
    max_retries: int = MAX_RETRIES,
) -> Optional[Any]:
    """
    GET sur une API JSON avec retries et backoff.

    Retourne la réponse parsée, ou None en cas d'erreur réseau / non-JSON.
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = _session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            logger.warning("fetch_json error (%d/%d) %s: %s",
                           attempt, max_retries, url, e)
            polite_sleep(delay * attempt)
            continue

        if resp.status_code in RETRYABLE_STATUS:
            logger.warning("fetch_json status %d (%d/%d) %s",
                           resp.status_code, attempt, max_retries, url)
            polite_sleep(delay * attempt)
            continue

        if resp.status_code != 200:
            logger.warning("fetch_json status %d (non-retryable) %s",
                           resp.status_code, url)
            return None

        try:
            return resp.json()
        except ValueError:
            logger.warning("fetch_json non-JSON response %s", url)
            return None

    logger.warning("fetch_json gave up after %d attempts: %s", max_retries, url)
    return None


# -------------------------
# Génération d'identifiant stable
# -------------------------

def generate_stable_id(source: str, external_id: str) -> str:
    """Identifiant unique et stable pour dédupliquer une annonce."""
    raw = f"{source}:{external_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# =========================
# Normalisation des données
# =========================

def normalize_price(raw_price: str) -> Optional[float]:
    """
    Convertit un prix texte en float (euros, entier).

    Gère les espaces, espaces insécables, points de milliers, préfixes
    et suffixes ('à partir de', 'FAI', '€'...).

    Exemples :
    '680 000 €'          -> 680000.0
    'Prix : 1.250.000'   -> 1250000.0
    'à partir de 250000' -> 250000.0
    """
    if not raw_price:
        return None
    s = raw_price.replace("\xa0", " ").lower()
    match = re.search(r"\d[\d\s\. ]*", s)
    if not match:
        return None
    digits = re.sub(r"[^\d]", "", match.group(0))
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def normalize_surface(raw_surface: str) -> Optional[float]:
    """
    Convertit une surface texte en float (m², décimales possibles).

    Exemples :
    '193 m²'        -> 193.0
    '85,5 m²'       -> 85.5
    'Surface 75 m2' -> 75.0
    """
    if not raw_surface:
        return None
    s = raw_surface.replace("\xa0", " ").lower()
    match = re.search(r"\d+(?:[.,]\d+)?", s)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


# =========================
# Helpers métier partagés
# =========================

def canonical_city(raw: Optional[str]) -> Optional[str]:
    """
    Forme canonique d'un nom de ville, partagée par toutes les sources ET par
    la requête d'analyse (market_stats), pour que la même commune écrite
    différemment selon les agences s'agrège sur la même clé.

    Stratégie : suppression des accents, séparateurs unifiés (espaces et tirets
    -> tiret unique), capitalisation par segment. Ainsi 'Montigny-lès-Metz',
    'Montigny Les Metz' et 'MONTIGNY-LES-METZ' -> 'Montigny-Les-Metz'.

    Retourne None / chaîne vide tels quels (pas de valeur factice).
    """
    if not raw:
        return raw
    stripped = unicodedata.normalize("NFD", raw.strip())
    stripped = "".join(c for c in stripped if unicodedata.category(c) != "Mn")
    segments = [s for s in re.split(r"[\s\-]+", stripped.lower()) if s]
    return "-".join(s.capitalize() for s in segments)


def infer_property_type(text: str) -> str:
    """Déduction simple du type de bien depuis un texte libre."""
    t = (text or "").lower()
    if any(k in t for k in ("maison", "villa", "propriété", "pavillon", "demeure")):
        return "maison"
    return "appartement"


# Quartiers de Metz et communes limitrophes couramment cités par les agences
# du Grand Metz. Ordre : libellés longs avant libellés courts pour éviter les
# faux positifs lors du matching.
_KNOWN_LOCALITIES = [
    "le ban-saint-martin",
    "montigny-lès-metz",
    "montigny-les-metz",
    "longeville-lès-metz",
    "longeville-les-metz",
    "saint-julien-lès-metz",
    "saint-julien-les-metz",
    "scy-chazelles",
    "devant-les-ponts",
    "grange-aux-bois",
    "nouvelle ville",
    "plantières",
    "plantieres",
    "bellecroix",
    "vallières",
    "vallieres",
    "la patrotte",
    "outre-seille",
    "technopôle",
    "technopole",
    "queuleu",
    "sablon",
    "magny",
    "borny",
    "woippy",
    "plappeville",
    "lessy",
    "marly",
    "augny",
    "centre-ville",
    "centre",
]


def extract_district(text: str) -> Optional[str]:
    """
    Extrait un quartier / commune connu du Grand Metz depuis un texte.

    Retourne None si rien n'est reconnu (et non une valeur factice, pour ne
    pas fausser le filtrage des comparables).
    """
    if not text:
        return None
    lowered = text.lower()
    for locality in _KNOWN_LOCALITIES:
        if locality in lowered:
            return locality.title()
    return None
