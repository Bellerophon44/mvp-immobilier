import requests
import hashlib
from typing import Any, Optional

# -------------------------
# Configuration HTTP
# -------------------------

HEADERS = {
    "User-Agent": "MVP-Immobilier-Research-Bot/1.0 (usage interne, faible fréquence)"
}

REQUEST_TIMEOUT = 10  # secondes


# -------------------------
# Téléchargement sécurisé de page
# -------------------------

def fetch_page(url: str) -> Optional[str]:
    """
    Télécharge une page HTML de manière simple et contrôlée.
    Retourne None en cas d’erreur.
    """
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.text
    except Exception:
        return None


def fetch_json(url: str, params: Optional[dict] = None) -> Optional[Any]:
    """
    Effectue une requête GET et retourne la réponse parsée en JSON.
    Retourne None en cas d’erreur réseau ou de réponse non-JSON.
    """
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


# -------------------------
# Génération d’identifiant stable
# -------------------------

def generate_stable_id(source: str, external_id: str) -> str:
    """
    Génère un identifiant unique pour chaque annonce.

    Permet d’éviter les doublons dans la base.
    """
    raw = f"{source}:{external_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# =========================
# Normalisation des données
# =========================

def normalize_price(raw_price: str) -> Optional[float]:
    """
    Convertit un prix texte en float.

    Exemple :
    '680 000 €' -> 680000.0
    """
    try:
        cleaned = (
            raw_price.replace("€", "")
            .replace(" ", "")
            .replace("\xa0", "")
        )
        return float(cleaned)
    except Exception:
        return None


def normalize_surface(raw_surface: str) -> Optional[float]:
    """
    Convertit une surface texte en float.

    Exemple :
    '193 m²' -> 193.0
    """
    try:
        cleaned = (
            raw_surface.replace("m²", "")
            .replace(" ", "")
            .replace("\xa0", "")
        )
        return float(cleaned)
    except Exception:
        return None
