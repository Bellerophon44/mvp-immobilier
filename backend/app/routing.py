"""Temps de trajet reels via Google Route Matrix (couche C de l'« Ancrage local »).

Point d'appel unique du client Google Route Matrix (Routes API). Le client HTTPS
est injectable (parametre `client`) pour rester testable sans reseau ; en
production il est construit a partir de `GOOGLE_MAPS_API_KEY`.

Garde-fous (CGU Google / robustesse) :
- repli SILENCIEUX (None par POI) si la cle est absente, le reseau echoue ou la
  reponse est invalide ; ne leve JAMAIS ;
- cache memoire court (TTL 10 min, par process) ; JAMAIS de persistance disque/DB.
"""

import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger("routing")

_ROUTE_MATRIX_URL = (
    "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
)
_TIMEOUT = 4
_CACHE_TTL_SECONDS = 10 * 60

# `travelMode` accepte par l'API Route Matrix. Un seul travelMode par requete.
_TRAVEL_MODES = {"WALK", "DRIVE", "BICYCLE", "TRANSIT"}

# Etat partage de module : (round(lat,5), round(lon,5), poi_id, mode) ->
# (timestamp, resultat|None). Memoire pure, jamais persiste (CGU Google).
_CACHE: Dict[Tuple[float, float, str, str], Tuple[float, Optional[dict]]] = {}


def reset_routing_cache() -> None:
    """Vide le cache memoire. Utilise par la fixture d'isolation (lecon 9.7/9.9)."""
    _CACHE.clear()


class RoutesClient:
    """Encapsule l'appel HTTPS au Route Matrix. Une methode par requete :
    `compute_route_matrix(origin, destinations, mode)` -> {poi_id: dict|None},
    chaque dict portant `distance_m`/`duration_s` bruts (None si pas de route)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def compute_route_matrix(
        self,
        origin: Tuple[float, float],
        destinations: Dict[str, Tuple[float, float]],
        mode: str,
    ) -> Dict[str, Optional[dict]]:
        poi_ids = list(destinations)
        payload = {
            "origins": [_waypoint(origin)],
            "destinations": [_waypoint(destinations[p]) for p in poi_ids],
            "travelMode": mode,
        }
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": (
                "originIndex,destinationIndex,duration,distanceMeters,condition"
            ),
            "Content-Type": "application/json",
        }
        resp = requests.post(
            _ROUTE_MATRIX_URL, json=payload, headers=headers, timeout=_TIMEOUT
        )
        resp.raise_for_status()
        elements = resp.json() or []

        out: Dict[str, Optional[dict]] = {p: None for p in poi_ids}
        for el in elements:
            idx = el.get("destinationIndex")
            if idx is None or not (0 <= idx < len(poi_ids)):
                continue
            poi_id = poi_ids[idx]
            condition = el.get("condition")
            if condition is not None and condition != "ROUTE_EXISTS":
                continue
            distance_m = el.get("distanceMeters")
            duration_s = _parse_duration(el.get("duration"))
            if distance_m is None or duration_s is None:
                continue
            out[poi_id] = {
                "distance_m": int(distance_m),
                "duration_s": int(duration_s),
            }
        return out


def _waypoint(coord: Tuple[float, float]) -> dict:
    lat, lon = coord
    return {
        "waypoint": {
            "location": {"latLng": {"latitude": lat, "longitude": lon}}
        }
    }


def _parse_duration(value: Any) -> Optional[int]:
    """La duree Route Matrix est une chaine type '480s'."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if text.endswith("s"):
        text = text[:-1]
    try:
        return int(round(float(text)))
    except ValueError:
        return None


def _build_client() -> Optional[RoutesClient]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return None
    return RoutesClient(api_key)


def compute_travel_times(
    origin: Tuple[float, float],
    destinations: Dict[str, Tuple[float, float]],
    mode: str,
    client: Optional[RoutesClient] = None,
) -> Dict[str, Optional[dict]]:
    """Pour chaque POI de `destinations` ({poi_id: (lat, lon)}), renvoie
    {poi_id: {"mode": <mode>, "distance_m": int, "duration_s": int}} ou
    {poi_id: None} si pas de route / reponse invalide pour ce POI.

    Repli SILENCIEUX : renvoie {poi_id: None} pour TOUS les POI si la cle est
    absente, le reseau echoue, ou la reponse est invalide. Ne leve jamais."""
    poi_ids = list(destinations)
    if mode not in _TRAVEL_MODES:
        logger.info("routing: mode inconnu %r, repli None partout", mode)
        return {p: None for p in poi_ids}

    lat_r, lon_r = round(origin[0], 5), round(origin[1], 5)

    # Repartition cache hit / a router. Le cache est par POI : deux origines
    # quasi identiques (arrondi 5 decimales) partagent leurs entrees.
    cached: Dict[str, Optional[dict]] = {}
    to_route: Dict[str, Tuple[float, float]] = {}
    now = time.time()
    for poi_id in poi_ids:
        key = (lat_r, lon_r, poi_id, mode)
        item = _CACHE.get(key)
        if item is not None and now - item[0] <= _CACHE_TTL_SECONDS:
            cached[poi_id] = item[1]
        else:
            to_route[poi_id] = destinations[poi_id]

    out: Dict[str, Optional[dict]] = dict.fromkeys(poi_ids)
    out.update(cached)

    if not to_route:
        return out

    if client is None:
        # Cle absente : repli immediat, AUCUN client construit, aucun appel
        # reseau, pas d'exception (on ne touche pas a _build_client sans cle).
        if not os.getenv("GOOGLE_MAPS_API_KEY"):
            logger.info("routing: GOOGLE_MAPS_API_KEY absente, repli vol d'oiseau")
            for poi_id in to_route:
                out[poi_id] = None
            return out
        client = _build_client()
    if client is None:
        logger.info("routing: client indisponible, repli vol d'oiseau")
        for poi_id in to_route:
            out[poi_id] = None
        return out

    raw: Dict[str, Optional[dict]] = {}
    try:
        raw = client.compute_route_matrix((origin[0], origin[1]), to_route, mode)
    except Exception:
        logger.exception("routing: appel client en echec, repli vol d'oiseau")
        raw = {}

    for poi_id in to_route:
        result = _normalize_element(raw.get(poi_id), mode)
        out[poi_id] = result
        _CACHE[(lat_r, lon_r, poi_id, mode)] = (now, result)

    return out


def _normalize_element(element: Any, mode: str) -> Optional[dict]:
    if not isinstance(element, dict):
        return None
    distance_m = element.get("distance_m")
    duration_s = element.get("duration_s")
    if not isinstance(distance_m, (int, float)) or not isinstance(
        duration_s, (int, float)
    ):
        return None
    return {
        "mode": mode,
        "distance_m": int(distance_m),
        "duration_s": int(duration_s),
    }
