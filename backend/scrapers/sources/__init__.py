"""Package des sources de scraping.

`load_all()` importe automatiquement chaque module de ce package, ce qui
déclenche leurs décorateurs `@register`. Ajouter une nouvelle agence se
résume donc à déposer un fichier `scrapers/sources/<agence>.py` : il est
collecté sans toucher au job d'ingestion ni au diagnostic.
"""

import importlib
import pkgutil


def load_all() -> list[str]:
    """Importe tous les modules de sources et retourne leurs noms."""
    loaded = []
    for _, modname, _ in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{modname}")
        loaded.append(modname)
    return loaded
