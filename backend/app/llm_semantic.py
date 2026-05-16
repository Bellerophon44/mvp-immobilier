import os
import time
import hashlib
from typing import Dict, Any

from openai import OpenAI


# =====================
# CONFIGURATION OPENAI
# =====================

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

MODEL_NAME = "gpt-4.1-mini"
TEMPERATURE = 0.2


# =====================
# CACHE SIMPLE EN MÉMOIRE
# =====================

_CACHE = {}
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 jours


def _normalize_text(text: str) -> str:
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
        del _CACHE[key]
        return None

    return value


def _set_cache(key: str, value: dict):
    _CACHE[key] = (time.time(), value)


# =====================
# PROMPTS IA
# =====================

SYSTEM_PROMPT = """
Tu es un assistant spécialisé en analyse d'annonces immobilières françaises.

Ton rôle n’est PAS d’estimer un prix.
Tu dois analyser la qualité de l’information et les risques.

Tu es prudent, neutre, explicable et factuel.
Tu n’inventes pas.
"""

USER_PROMPT_TEMPLATE = """
Analyse le texte d’annonce immobilière ci-dessous et retourne UNIQUEMENT un objet JSON STRICT
respectant EXACTEMENT ce format :

{
  "transparency_score": number,
  "verdict": string,
  "risk_level": string,
  "summary": string,
  "risk_summary": string,
  "to_check": [string],
  "questions": [string],
  "negotiation_levers": [string]
}

Contraintes :
- Aucun prix
- Aucun conseil juridique
- Aucun calcul de valeur
- Maximum 2 phrases dans résumé

Texte :
---
{raw_text}
---
"""


# =====================
# FONCTION PRINCIPALE
# =====================

def analyze_semantic(raw_text: str) -> Dict[str, Any]:
    """
    Analyse complète du texte d'annonce via IA.
    """

    # ---------- Cache ----------
    cache_key = _hash_text(raw_text)
    cached = _get_from_cache(cache_key)
    if cached:
        return cached

    # ---------- Appel OpenAI ----------
    try:
        response = client.responses.create(
            model=MODEL_NAME,
            temperature=TEMPERATURE,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(raw_text=raw_text)
                }
            ],
            response_format={"type": "json_object"}
        )

        result = response.output_parsed

    except Exception:
        # fallback sécurisé si OpenAI échoue
        return {
            "transparency_score": 50,
            "verdict": "Moyenne",
            "risk_level": "Modéré",
            "summary": "Analyse indisponible.",
            "risk_summary": "Impossible d'évaluer les risques.",
            "to_check": [],
            "questions": [],
            "negotiation_levers": []
        }

    # ---------- Nettoyage sortie ----------
    semantic_output = {
        "transparency_score": int(result.get("transparency_score", 50)),
        "verdict": result.get("verdict", "Moyenne"),
        "risk_level": result.get("risk_level", "Modéré"),
        "summary": result.get("summary", ""),
        "risk_summary": result.get("risk_summary", ""),
        "to_check": result.get("to_check", []),
        "questions": result.get("questions", []),
        "negotiation_levers": result.get("negotiation_levers", [])
    }

    _set_cache(cache_key, semantic_output)

    return semantic_output
