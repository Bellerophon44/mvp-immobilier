import json
import os
import time
import hashlib
from typing import Dict, Any, Optional

from openai import OpenAI


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
TEMPERATURE = 0.2


_CACHE: Dict[str, Any] = {}
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _hash_text(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def _get_from_cache(key: str) -> Optional[dict]:
    item = _CACHE.get(key)
    if not item:
        return None
    timestamp, value = item
    if time.time() - timestamp > CACHE_TTL_SECONDS:
        del _CACHE[key]
        return None
    return value


def _set_cache(key: str, value: dict) -> None:
    _CACHE[key] = (time.time(), value)


SYSTEM_PROMPT = (
    "Tu es un assistant spécialisé en analyse d'annonces immobilières françaises. "
    "Ton rôle n'est PAS d'estimer un prix. "
    "Tu dois analyser la qualité de l'information, les risques, "
    "et extraire les données structurées observables dans l'annonce. "
    "Tu es prudent, neutre, explicable et factuel. Tu n'inventes pas."
)


USER_PROMPT_TEMPLATE = """Analyse le texte d'annonce immobilière ci-dessous et retourne UNIQUEMENT un objet JSON STRICT respectant EXACTEMENT ce format :

{{
  "transparency_score": number,
  "verdict": string,
  "risk_level": string,
  "summary": string,
  "risk_summary": string,
  "to_check": [string],
  "questions": [string],
  "negotiation_levers": [string],
  "listing": {{
    "city": string | null,
    "district": string | null,
    "property_type": string | null,
    "surface_m2": number | null,
    "price_total": number | null
  }}
}}

Règles :
- Aucun prix estimé, aucun calcul de valeur.
- Aucun conseil juridique.
- Maximum 2 phrases dans `summary` et `risk_summary`.
- `transparency_score` est un entier entre 0 et 100.
- `verdict` ∈ ["Bonne", "Moyenne", "Faible"].
- `risk_level` ∈ ["Faible", "Modéré", "Élevé"].
- `property_type` ∈ ["appartement", "maison", null].
- Pour `listing`, n'extraire que ce qui est EXPLICITEMENT présent dans le texte ; sinon `null`.

Texte :
---
{raw_text}
---
"""


_FALLBACK = {
    "transparency_score": 50,
    "verdict": "Moyenne",
    "risk_level": "Modéré",
    "summary": "Analyse indisponible.",
    "risk_summary": "Impossible d'évaluer les risques.",
    "to_check": [],
    "questions": [],
    "negotiation_levers": [],
    "listing": {
        "city": None,
        "district": None,
        "property_type": None,
        "surface_m2": None,
        "price_total": None,
    },
}


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def analyze_semantic(raw_text: str) -> Dict[str, Any]:
    cache_key = _hash_text(raw_text)
    cached = _get_from_cache(cache_key)
    if cached:
        return cached

    user_prompt = USER_PROMPT_TEMPLATE.format(raw_text=raw_text)

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            temperature=TEMPERATURE,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
    except Exception:
        return dict(_FALLBACK)

    raw_listing = result.get("listing") or {}
    listing = {
        "city": raw_listing.get("city"),
        "district": raw_listing.get("district"),
        "property_type": raw_listing.get("property_type"),
        "surface_m2": _coerce_float(raw_listing.get("surface_m2")),
        "price_total": _coerce_float(raw_listing.get("price_total")),
    }

    semantic_output = {
        "transparency_score": _coerce_int(result.get("transparency_score"), 50),
        "verdict": result.get("verdict") or "Moyenne",
        "risk_level": result.get("risk_level") or "Modéré",
        "summary": result.get("summary") or "",
        "risk_summary": result.get("risk_summary") or "",
        "to_check": result.get("to_check") or [],
        "questions": result.get("questions") or [],
        "negotiation_levers": result.get("negotiation_levers") or [],
        "listing": listing,
    }

    _set_cache(cache_key, semantic_output)
    return semantic_output
