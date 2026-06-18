"""Cas d'evaluation de la refonte des leviers de negociation (issue #123,
chantier negotiation-levers-review).

Probleme corrige : la section « Leviers de negociation » reprenait les POINTS
FORTS du bien (favorables au vendeur) au lieu d'elements mobilisables par
l'acheteur pour discuter le prix a la baisse. Desormais deux intentions
distinctes cote LLM :
- `highlights` : atouts factuels du bien (objective sa valeur) ;
- `negotiation_levers` : uniquement des elements DEFAVORABLES / relativisants
  (travaux, DPE faible, nuisances...), cote acheteur.

L'annonce de cases/issue_123.txt est SYNTHETIQUE (reecriture fictive melant atouts
nets et points faibles nets, CONTEXT §11.3, repo public). Un seul appel LLM reel
par run (fixture module-scoped). Assertions thematiques (tolerantes a la
formulation), bloquantes : une PR de prompt qui re-melange les deux intentions
met le job evals au rouge.
"""

import pytest

from app.llm_semantic import analyze_semantic


# Atouts attendus (presents et positifs dans le texte synthetique).
_POSITIVE_TOKENS = ("jardin", "garage", "terrasse")
# Points faibles attendus, mobilisables a la baisse.
_WEAK_TOKENS = ("travaux", "rénov", "renov", "toiture", "dpe", "passoire",
                "nuisance", "sonore", "route", "rafraîch", "rafraich")


@pytest.fixture(scope="module")
def semantic_levers(load_case):
    return analyze_semantic(load_case("issue_123"))


def test_extraction_property_type_maison(semantic_levers):
    assert semantic_levers["listing"]["property_type"] == "maison"


def test_extraction_dpe_f(semantic_levers):
    assert semantic_levers["listing"]["dpe"] == "F"


def test_highlights_non_vides_et_positifs(semantic_levers):
    """Les atouts factuels du bien sont surfaces (section dediee)."""
    highlights = semantic_levers["highlights"]
    assert len(highlights) >= 1
    blob = " ".join(highlights).casefold()
    assert any(tok in blob for tok in _POSITIVE_TOKENS), (
        f"Aucun atout positif reconnu dans highlights : {highlights}"
    )


def test_leviers_contiennent_un_point_faible(semantic_levers):
    """Au moins un levier porte sur un element defavorable / relativisant."""
    levers = semantic_levers["negotiation_levers"]
    assert len(levers) >= 1, "Des points faibles nets existent : leviers attendus"
    blob = " ".join(levers).casefold()
    assert any(tok in blob for tok in _WEAK_TOKENS), (
        f"Aucun point faible reconnu dans les leviers : {levers}"
    )


def test_leviers_ne_reprennent_pas_les_atouts(semantic_levers):
    """Regression centrale : un atout pur (le jardin) ne doit pas etre presente
    comme un levier de negociation."""
    levers_blob = " ".join(semantic_levers["negotiation_levers"]).casefold()
    assert "jardin" not in levers_blob, (
        f"Un atout (jardin) a fui dans les leviers : {semantic_levers['negotiation_levers']}"
    )
