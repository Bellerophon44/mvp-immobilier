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
import urllib.request

import scrapers.sources.bienici  # noqa: F401 — triggers @register
import scrapers.sources.site_local  # noqa: F401 — triggers @register
from scrapers.registry import run_all

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("push_comparables")

BATCH_SIZE = 1000
TIMEOUT = 60


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


def main() -> int:
    backend_url = os.getenv("BACKEND_URL")
    token = os.getenv("ADMIN_TOKEN")
    if not backend_url or not token:
        logger.error("BACKEND_URL et ADMIN_TOKEN sont requis.")
        return 2

    logger.info("Collecte des comparables...")
    listings = run_all()
    if not listings:
        logger.warning("Aucune annonce collectée — rien à pousser.")
        return 1

    items = [l.to_dict() for l in listings]
    logger.info("%d comparables collectés. Envoi vers %s", len(items), backend_url)

    total_saved = 0
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start:start + BATCH_SIZE]
        try:
            result = _post_batch(backend_url, token, batch)
        except Exception as e:
            logger.error("Échec d'envoi du batch %d: %s", start // BATCH_SIZE, e)
            return 1
        logger.info("Batch %d: %s", start // BATCH_SIZE, result)
        total_saved += result.get("saved", 0)

    logger.info("Terminé. %d comparables enregistrés.", total_saved)
    return 0


if __name__ == "__main__":
    sys.exit(main())
