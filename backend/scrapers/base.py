import requests
import hashlib
from typing import Optional

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


# -------------------------
# Génération d’identifiant stable
# -------------------------

def generate_stable_id(source: str, external_id: str) -> str:
    """
    Génère un identifiant interne stable à partir :
