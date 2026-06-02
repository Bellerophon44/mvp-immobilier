import json
import logging
import os
import time
import hashlib
from typing import Dict, Any, Optional

from openai import OpenAI

logger = logging.getLogger("llm_semantic")
logging.basicConfig(level=logging.INFO)


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
    "price_total": number | null,
    "dpe": string | null,
    "construction_year": number | null,
    "floor": number | null,
    "has_elevator": boolean | null,
    "has_terrace": boolean | null,
    "has_balcony": boolean | null,
    "has_cellar": boolean | null,
    "parking": number | null,
    "bedrooms": number | null,
    "condo_fees": number | null
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
- `dpe` : lettre de classe énergie ∈ ["A","B","C","D","E","F","G"] si présente, sinon null (ne pas confondre avec le GES).
- `construction_year` : année de construction (entier) si EXPLICITEMENT mentionnée, sinon null.
- `floor` : numéro d'étage (entier ; rez-de-chaussée = 0) si mentionné, sinon null.
- `has_elevator`, `has_terrace`, `has_balcony`, `has_cellar` : true/false UNIQUEMENT si l'annonce le précise, sinon null (ne pas supposer).
- `parking`, `bedrooms` : entier si mentionné, sinon null.
- `condo_fees` : charges annuelles de copropriété en euros (entier) si mentionnées, sinon null.
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
        "dpe": None,
        "construction_year": None,
        "floor": None,
        "has_elevator": None,
        "has_terrace": None,
        "has_balcony": None,
        "has_cellar": None,
        "parking": None,
        "bedrooms": None,
        "condo_fees": None,
    },
}


_VALID_DPE = {"A", "B", "C", "D", "E", "F", "G"}


def _coerce_dpe(value):
    if isinstance(value, str) and value.strip().upper()[:1] in _VALID_DPE:
        return value.strip().upper()[:1]
    return None


def _coerce_year(value):
    try:
        y = int(value)
    except (TypeError, ValueError):
        return None
    return y if 1600 <= y <= 2100 else None


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


def _coerce_bool(value):
    return value if isinstance(value, bool) else None


def _coerce_int_opt(value):
    """Entier >= 0 (étage, places, chambres), sinon None. 0 reste valide (rdc)."""
    if isinstance(value, bool):
        return None
    try:
        i = int(value)
    except (TypeError, ValueError):
        return None
    return i if i >= 0 else None


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
    except Exception as e:
        logger.exception(
            "LLM call failed (model=%s, key_set=%s): %s",
            MODEL_NAME,
            bool(os.getenv("OPENAI_API_KEY")),
            e,
        )
        return dict(_FALLBACK)

    raw_listing = result.get("listing") or {}
    listing = {
        "city": raw_listing.get("city"),
        "district": raw_listing.get("district"),
        "property_type": raw_listing.get("property_type"),
        "surface_m2": _coerce_float(raw_listing.get("surface_m2")),
        "price_total": _coerce_float(raw_listing.get("price_total")),
        "dpe": _coerce_dpe(raw_listing.get("dpe")),
        "construction_year": _coerce_year(raw_listing.get("construction_year")),
        "floor": _coerce_int_opt(raw_listing.get("floor")),
        "has_elevator": _coerce_bool(raw_listing.get("has_elevator")),
        "has_terrace": _coerce_bool(raw_listing.get("has_terrace")),
        "has_balcony": _coerce_bool(raw_listing.get("has_balcony")),
        "has_cellar": _coerce_bool(raw_listing.get("has_cellar")),
        "parking": _coerce_int_opt(raw_listing.get("parking")),
        "bedrooms": _coerce_int_opt(raw_listing.get("bedrooms")),
        "condo_fees": _coerce_float(raw_listing.get("condo_fees")),
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
