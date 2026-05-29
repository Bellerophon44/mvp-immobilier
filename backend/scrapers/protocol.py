from typing import Protocol, runtime_checkable

from scrapers.models import PropertyListing


@runtime_checkable
class ScraperProtocol(Protocol):
    def scrape(self) -> list[PropertyListing]:
        ...
