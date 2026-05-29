"""
Kept for backward compatibility — do not add new logic here.
Use scrapers/sources/site_local.py and the registry instead.
"""
from scrapers.sources.site_local import SiteLocalScraper


def scrape_site_local_metz() -> list:
    return [l.to_dict() for l in SiteLocalScraper().scrape()]
