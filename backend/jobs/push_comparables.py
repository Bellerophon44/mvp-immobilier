"""
Collecte les comparables (registre de scrapers) et les pousse vers le
backend de prod via l'endpoint protégé /admin/comparables.

Usage (depuis backend/) :
    BACKEND_URL=https://...fly.dev ADMIN_TOKEN=xxx python -m jobs.push_comparables

La collecte tourne ici (réseau OK), l'écriture en base se fait côté
backend sur son volume persistant. Aucun SSH, aucun transfert de fichier.
"""

import json
import logging
import os
import sys
import time
import urllib.request

from scrapers.sources import load_all
from scrapers.registry import run_all

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("push_comparables")

BATCH_SIZE = 1000
TIMEOUT = 120
# Un batch peut echouer de facon transitoire (timeout cote serveur sous charge,
# 500 pendant une ecriture SQLite concurrente). On reessaie avec backoff avant
# d'abandonner le batch, pour ne pas perdre des communes entieres de la queue.
MAX_RETRIES = 3
RETRY_BACKOFF_S = 2.0


_REQUIRED_STR = ("id", "source", "city", "property_type")


def _is_valid(item: dict) -> bool:
    """Garde-fou client : un item incomplet (ex. ville absente) ferait échouer
    tout le batch en 422 côté API. On les écarte avant l'envoi."""
    for key in _REQUIRED_STR:
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            return False
    surface, price = item.get("surface_m2"), item.get("price_total")
    return (isinstance(surface, (int, float)) and not isinstance(surface, bool)
            and isinstance(price, (int, float)) and not isinstance(price, bool)
            and surface > 0 and price > 0)


def _post_batch(backend_url: str, token: str, items: list) -> dict:
    url = backend_url.rstrip("/") + "/admin/comparables"
    data = json.dumps({"items": items}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Admin-Token": token,
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_batch_with_retry(backend_url: str, token: str, items: list,
                           batch_idx: int) -> dict:
    """Envoie un batch avec reessais a backoff exponentiel. Releve la derniere
    exception si tous les essais echouent (le batch est alors compte en echec)."""
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _post_batch(backend_url, token, items)
        except Exception as e:  # noqa: BLE001 - on reessaie sur toute erreur reseau/HTTP
            last_exc = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_S * (2 ** (attempt - 1))
                logger.warning("Batch %d essai %d/%d echoue (%s) — retry dans %.0fs.",
                               batch_idx, attempt, MAX_RETRIES, e, wait)
                time.sleep(wait)
    assert last_exc is not None
    raise last_exc


def main() -> int:
    backend_url = os.getenv("BACKEND_URL")
    token = os.getenv("ADMIN_TOKEN")
    if not backend_url or not token:
        logger.error("BACKEND_URL et ADMIN_TOKEN sont requis.")
        return 2

    logger.info("Sources chargées : %s", load_all())
    listings = run_all()
    if not listings:
        logger.warning("Aucune annonce collectée — rien à pousser.")
        return 1

    raw = [l.to_dict() for l in listings]
    items = [d for d in raw if _is_valid(d)]
    dropped = len(raw) - len(items)
    if dropped:
        logger.warning("%d item(s) écartés (champs requis manquants).", dropped)
    logger.info("%d comparables collectés. Envoi vers %s", len(items), backend_url)

    total_saved = 0
    failed_batches = 0
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start:start + BATCH_SIZE]
        try:
            result = _post_batch_with_retry(backend_url, token, batch,
                                            start // BATCH_SIZE)
        except Exception as e:
            # On n'abandonne pas tout le run pour un batch : les suivants
            # (notamment les grandes surfaces, balayées en dernier) doivent passer.
            logger.error("Échec d'envoi du batch %d: %s", start // BATCH_SIZE, e)
            failed_batches += 1
            continue
        logger.info("Batch %d: %s", start // BATCH_SIZE, result)
        total_saved += result.get("saved", 0)

    logger.info("Terminé. %d comparables enregistrés (%d batch(es) en échec).",
                total_saved, failed_batches)
    return 1 if failed_batches else 0


if __name__ == "__main__":
    sys.exit(main())
