import logging

import scrapers.sources.bienici  # noqa: F401 — triggers @register
import scrapers.sources.site_local  # noqa: F401 — triggers @register
from scrapers.registry import run_all
from ingestion.save import save_comparables

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run():
    logger.info("Démarrage de la collecte des comparables...")

    listings = run_all()

    if not listings:
        logger.warning("Aucune annonce récupérée.")
        return

    saved = save_comparables([l.to_dict() for l in listings])
    logger.info("%d annonces comparables enregistrées en base.", saved)


if __name__ == "__main__":
    run()
