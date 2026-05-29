import logging
from typing import Dict, Type

from scrapers.models import PropertyListing
from scrapers.protocol import ScraperProtocol

logger = logging.getLogger(__name__)

_registry: Dict[str, Type[ScraperProtocol]] = {}


def register(name: str):
    """Decorator to register a scraper class under a given name."""
    def decorator(cls: Type[ScraperProtocol]):
        _registry[name] = cls
        return cls
    return decorator


def run_all() -> list[PropertyListing]:
    """Run every registered scraper and aggregate results."""
    results = []

    for name, scraper_cls in _registry.items():
        try:
            listings = scraper_cls().scrape()
            logger.info("Scraper '%s' returned %d listings.", name, len(listings))
            results.extend(listings)
        except Exception:
            logger.exception("Scraper '%s' failed — skipping.", name)

    return results
