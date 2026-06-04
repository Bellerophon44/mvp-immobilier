"""Géocodage d'adresse (couche C de l'« Ancrage local »).

Traduit une adresse texte en coordonnées (lat, lon) via la Base Adresse
Nationale (api-adresse.data.gouv.fr) : gratuite, sans clé, et qui renvoie un
score de confiance. Aucune coordonnée n'est inventée ici.

Stratégie de prudence :
- repli silencieux (None) sur toute erreur réseau / score faible / hors Moselle,
  pour que l'analyse retombe sur le profil de quartier (couches A/B) ;
- cache mémoire (comme le LLM) pour ne pas re-géocoder la même adresse ;
- périmètre département 57 vérifié sur le code postal renvoyé.
"""

import logging
import time
from typing import Dict, Optional

import requests

logger = logging.getLogger("geocode")

_BAN_URL = "https://api-adresse.data.gouv.fr/search/"
_HEADERS = {"User-Agent": "mvp-immobilier/1.0 (coherence-immo)"}
_TIMEOUT = 6
# En-dessous, le résultat BAN est trop incertain pour s'y fier (on retombe alors
# sur le quartier). 0.4 laisse passer les adresses partielles plausibles.
_MIN_SCORE = 0.4
_IN_SCOPE_DEPARTMENT = "57"

_CACHE: Dict[str, Optional[dict]] = {}
_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60


def _normalize(address: str) -> str:
    return " ".join(address.lower().strip().split())


def _get_cache(key: str):
    item = _CACHE.get(key)
    if item is None:
        return None
    ts, value = item
    if time.time() - ts > _CACHE_TTL_SECONDS:
        del _CACHE[key]
        return None
    return value


def geocode_address(address: str, city_hint: str = "Metz") -> Optional[dict]:
    """(lat, lon, score, label) pour une adresse, ou None si non géocodable de
    façon fiable / hors périmètre / réseau indisponible.

    Le résultat (y compris None) est mis en cache : une adresse non géocodable ne
    sera pas retentée à chaque ré-analyse.
    """
    if not address or not address.strip():
        return None

    # On aide la BAN en ajoutant la ville si l'utilisateur ne l'a pas saisie.
    query = address.strip()
    if city_hint and city_hint.lower() not in query.lower():
        query = f"{query}, {city_hint}"

    key = _normalize(query)
    cached = _get_cache(key)
    if cached is not None or key in _CACHE:
        return cached

    result: Optional[dict] = None
    try:
        resp = requests.get(
            _BAN_URL,
            params={"q": query, "limit": 1},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        features = (resp.json() or {}).get("features") or []
        if features:
            feat = features[0]
            props = feat.get("properties") or {}
            coords = (feat.get("geometry") or {}).get("coordinates") or []
            score = props.get("score") or 0
            postcode = str(props.get("postcode") or "")
            in_scope = postcode.startswith(_IN_SCOPE_DEPARTMENT) or not postcode
            if len(coords) == 2 and score >= _MIN_SCORE and in_scope:
                lon, lat = coords[0], coords[1]
                result = {
                    "lat": float(lat),
                    "lon": float(lon),
                    "score": float(score),
                    "label": props.get("label") or query,
                }
            else:
                logger.info(
                    "Géocodage rejeté (score=%s, cp=%s) pour %r", score, postcode, query
                )
    except Exception as e:
        # Pas de cache négatif sur erreur réseau : l'adresse pourra être retentée.
        logger.warning("Géocodage indisponible pour %r: %s", query, e)
        return None

    _CACHE[key] = (time.time(), result)
    return result
