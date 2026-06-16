"""Cas d'evaluation LLM — issue #100, chantier A (AC16).

Verrouille que le LLM extrait bien « Sainte-Therese » comme micro-quartier
(`listing.district` et/ou `local_claims`) a partir d'un texte d'annonce
SYNTHETIQUE et fictif (cases/issue_100_A.txt ; jamais l'extrait pilote reel,
CONTEXT §11.3).

Politique evals (SPEC §4 AC16, lecons 2026-06-16 + 2026-06-12 evals-harness) :
- EXACTEMENT 1 site d'appel `analyze_semantic` dans CE module, dans une fixture
  `scope="module"` ; 0 appel hors module. Pas de cardinalite globale cross-module
  codee ici (chaque module porte son propre appel).
- toute fixture consommee par un xfail l'est AUSSI par au moins un test bloquant
  de la meme suite (la fixture `semantic_issue_100_A` alimente les sanity
  bloquantes ci-dessous ET l'oracle xfail) : un ERROR de setup met le job au
  rouge (lecon 2026-06-12).
- l'oracle LLM (extraction du micro-quartier) est `xfail(strict=False)` : son
  passage n'est pas garanti (le micro-quartier Sainte-Therese est plus fin que
  les quartiers courants).

Suite PAYANTE (vrais appels OpenAI) : jamais collectee par la suite gratuite
(backend/pytest.ini testpaths=tests) ; invocation `python -m pytest evals -q`.
"""

import pytest

from app.llm_semantic import analyze_semantic


@pytest.fixture(scope="module")
def semantic_issue_100_A(load_case):
    # SEUL point d'appel du LLM de ce module (AC14 : 1 appel par cas et par run).
    return analyze_semantic(load_case("issue_100_A"))


# ---------------------------------------------------------------------------
# Sanity d'extraction — BLOQUANTES (sans xfail).
# Consomment la meme fixture que l'oracle xfail -> un ERROR de setup (panne de
# l'appel LLM) met le job au rouge plutot que de devenir un XFAIL silencieux.
# ---------------------------------------------------------------------------

def test_extraction_city_metz(semantic_issue_100_A):
    city = (semantic_issue_100_A["listing"]["city"] or "").strip().casefold()
    assert city.startswith("metz")


def test_extraction_property_type_appartement(semantic_issue_100_A):
    assert semantic_issue_100_A["listing"]["property_type"] == "appartement"


def test_extraction_surface(semantic_issue_100_A):
    assert semantic_issue_100_A["listing"]["surface_m2"] == 68.0


def test_extraction_price_total(semantic_issue_100_A):
    assert semantic_issue_100_A["listing"]["price_total"] == 198000.0


# ---------------------------------------------------------------------------
# Oracle LLM — extraction du micro-quartier Sainte-Therese. xfail strict=False.
# ---------------------------------------------------------------------------

def _mentions_sainte_therese(text) -> bool:
    t = (text or "").casefold()
    # Tolere accent / sans accent / espace insecable autour du tiret.
    return "sainte-therese" in t or "sainte-thérèse" in t or "sainte therese" in t


@pytest.mark.xfail(
    strict=False,
    reason="Extraction du micro-quartier Sainte-Therese non garantie (plus fin "
    "que les quartiers courants) ; oracle de mesure, non bloquant.",
)
def test_llm_extrait_micro_quartier_sainte_therese(semantic_issue_100_A):
    """Le LLM doit faire surface 'Sainte-Therese' soit comme listing.district,
    soit dans un local_claim."""
    district = semantic_issue_100_A["listing"].get("district")
    claims_texts = [
        c.get("text") for c in (semantic_issue_100_A.get("local_claims") or [])
        if isinstance(c, dict)
    ]
    found = _mentions_sainte_therese(district) or any(
        _mentions_sainte_therese(t) for t in claims_texts
    )
    assert found, (
        "Sainte-Therese absente de listing.district "
        f"({district!r}) et des local_claims ({claims_texts!r})"
    )
