import os
import time
import hashlib
from typing import Dict, Any

from openai import OpenAI


# =====================
# Configuration OpenAI
# =====================

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

MODEL_NAME = "gpt-4.1-mini"   # fiable, peu coûteux, suffisant pour analyse sémantique
TEMPERATURE = 0.2            # faible créativité, forte stabilité


# =====================
# Cache simple en mémoire
# =====================

_CACHE = {}
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 jours


def _normalize_text(text: str) -> str:
    """Nettoie le texte pour un hash stable."""
    return " ".join(text.lower().strip().split())


def _hash_text(text: str) -> str:
    normalized = _normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _get_from_cache(key: str):
    item = _CACHE.get(key)
    if not item:
        return None

    timestamp, value = item
    if time.time() - timestamp > CACHE_TTL_SECONDS:
