"""Conftest de la suite d'evals (payante : VRAIS appels LLM).

Spec : docs/specs/evals-harness-SPEC.md (§3.3, §3.4). Cette suite n'est jamais
collectee par la suite gratuite (backend/pytest.ini, testpaths = tests) ; elle
s'invoque explicitement : `python -m pytest evals -q -rxX`.

Trois invariants poses ici, dans cet ordre :
1. DATABASE_PATH force vers un fichier jetable suffixe pid (jamais setdefault,
   lecon 9.7 durcie) AVANT tout import app.*/db.* — la chaine d'import de
   analysis.py touche db/.
2. Garde de cle : sans OPENAI_API_KEY reelle, echec EXPLICITE avant l'import de
   app.llm_semantic (qui instancie le client a l'import). Jamais de faux vert.
3. Reset du cache LLM en debut de session (lecon photo-evidence) : un rejeu
   dans la meme session mesurerait le cache, pas le modele.
"""

import os
import tempfile
from pathlib import Path

os.environ["DATABASE_PATH"] = os.path.join(
    tempfile.gettempdir(), f"mvp_evals_{os.getpid()}.db"
)

# Placeholders des suites gratuites (test.yml et tests/conftest.py) : une eval
# lancee avec l'un d'eux echouerait en silence cote OpenAI puis retomberait sur
# le fallback — la garde refuse donc explicitement ces valeurs (spec §3.3).
_REFUSED_KEYS = {"", "test-key-not-real", "test-key-not-used"}

_key = os.environ.get("OPENAI_API_KEY")
if _key is None or _key.strip() in _REFUSED_KEYS:
    raise RuntimeError(
        "OPENAI_API_KEY absente, vide ou placeholder de la suite gratuite : "
        "la suite evals exige une vraie cle (secret CI dedie avec usage limit, "
        "cf. docs/specs/evals-harness-SPEC.md §3.1). Abandon explicite avant "
        "tout import du client LLM — jamais de faux vert."
    )

import pytest

_CASES_DIR = Path(__file__).resolve().parent / "cases"


@pytest.fixture(scope="session", autouse=True)
def _reset_llm_cache():
    """Vide le cache memoire du module LLM au demarrage de session (AC10).

    Pas de clear par test en v1 : il forcerait un second appel payant pour le
    meme cas (spec §3.4)."""
    from app import llm_semantic

    llm_semantic._CACHE.clear()
    yield


@pytest.fixture(scope="session")
def load_case():
    """Lit evals/cases/<nom>.txt. Expose en fixture, jamais importe depuis le
    conftest sous un second nom de module (lecon cross-agence-inc1)."""

    def _load(name: str) -> str:
        return (_CASES_DIR / f"{name}.txt").read_text(encoding="utf-8")

    return _load
