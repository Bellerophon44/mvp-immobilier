"""Rate-limit en memoire (fenetre glissante, par IP), implementation maison.

Brique reutilisable exposee comme fabrique de dependance FastAPI (cf.
docs/specs/9.9-SPEC.md). Etat mono-instance (1 VM Fly), purge des timestamps
hors fenetre. L'IP sert uniquement de cle de bucket transitoire : jamais
persistee, jamais journalisee (critere RGPD §6 / critere 7).
"""

import itertools
import logging
import time
from collections import defaultdict, deque
from math import ceil
from typing import Callable, Deque, Dict, Tuple

from fastapi import HTTPException, Request

# Logger nomme sans IP : on n'emet qu'un compteur agrege d'evenements 429.
logger = logging.getLogger("rate_limit")

# Etat partage de module : (scope, IP) -> timestamps (time.monotonic) des hits
# retenus. Le scope distingue chaque limiteur : sans lui, deux endpoints aux
# seuils differents (/analyze limit=10, /feedback limit=60) partageraient le
# meme compteur pour une IP donnee, et les hits /feedback feraient deborder le
# seuil bien plus bas d'/analyze.
_buckets: Dict[Tuple[int, str], Deque[float]] = defaultdict(deque)

# Identifiant unique par limiteur, alloue a la fabrication de la dependance.
_scope_counter = itertools.count()


def reset_rate_limit_state() -> None:
    """Vide tous les buckets. Utilise par la fixture d'isolation (lecon 9.7)."""
    _buckets.clear()


def _resolve_ip(request: Request) -> str:
    fly_ip = request.headers.get("Fly-Client-IP")
    if fly_ip:
        return fly_ip.strip()

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop

    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def rate_limiter(limit: int, window_seconds: float) -> Callable:
    """Fabrique une dependance FastAPI limitant a `limit` requetes par fenetre
    glissante de `window_seconds` secondes et par IP. Au-dela : HTTPException 429
    avec en-tete Retry-After (entier, 1 <= n <= window).
    """

    scope = next(_scope_counter)

    def dependency(request: Request) -> None:
        now = time.monotonic()
        ip = _resolve_ip(request)
        bucket = _buckets[(scope, ip)]

        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            # Duree restante avant que le plus ancien hit de la fenetre n'expire.
            retry_after = ceil(bucket[0] + window_seconds - now)
            retry_after = max(1, min(retry_after, int(ceil(window_seconds))))
            logger.info("rate-limit 429 emitted (limit=%d)", limit)
            raise HTTPException(
                status_code=429,
                detail="Trop de requetes, reessayez plus tard.",
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)

    return dependency
