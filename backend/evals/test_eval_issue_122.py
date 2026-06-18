"""Cas d'evaluation de la refonte des leviers de negociation (issue #122,
retour-pilote « qualite section levier de negociation »).

Symptome rapporte : sur une annonce ENTIEREMENT POSITIVE (maison de ville en
parfait etat, jardin arbore, garage, terrasse avec vue...), la section
« Leviers de negociation » recopiait ces POINTS FORTS — favorables au vendeur —
au lieu d'elements mobilisables par l'acheteur a la baisse. Refonte : deux
intentions distinctes cote LLM :
- `highlights` : atouts factuels du bien (objective sa valeur) ;
- `negotiation_levers` : uniquement des elements DEFAVORABLES / relativisants ;
  liste VIDE si l'annonce ne revele rien de defavorable (jamais un atout recycle).

L'annonce de cases/issue_122.txt est SYNTHETIQUE : reecriture fictive reproduisant
le cas rapporte (tous atouts, aucun defaut net), jamais l'extrait reel ni l'URL
versionnes (CONTEXT §11.3, docs/pilotes/README.md, repo public). Un seul appel
LLM reel par run (fixture module-scoped). Assertions thematiques tolerantes a la
formulation, bloquantes : une PR de prompt qui re-melange les deux intentions met
le job evals au rouge.
"""

import pytest

from app.llm_semantic import analyze_semantic


# Atouts du bien, tels qu'affirmes dans l'annonce tout-positif. Aucun ne doit
# apparaitre comme un levier de negociation (regression centrale de l'issue #122).
_ATOUT_TOKENS = ("jardin", "garage", "terrasse", "vue", "parfait état",
                 "parfait etat", "véranda", "veranda", "dépendance", "dependance",
                 "calme")


@pytest.fixture(scope="module")
def semantic_levers(load_case):
    return analyze_semantic(load_case("issue_122"))


def test_extraction_property_type_maison(semantic_levers):
    assert semantic_levers["listing"]["property_type"] == "maison"


def test_highlights_non_vides_et_positifs(semantic_levers):
    """Les atouts factuels du bien sont bien surfaces (nouvelle section dediee),
    et non perdus : un acheteur doit pouvoir apprecier la valeur du bien."""
    highlights = semantic_levers["highlights"]
    assert len(highlights) >= 1, "Atouts attendus pour une annonce riche en points forts"
    blob = " ".join(highlights).casefold()
    assert any(tok in blob for tok in _ATOUT_TOKENS), (
        f"Aucun atout reconnu dans highlights : {highlights}"
    )


def test_aucun_atout_ne_fuit_dans_les_leviers(semantic_levers):
    """Regression centrale de l'issue #122 : les points forts du bien (jardin,
    garage, terrasse avec vue, parfait etat...) ne doivent JAMAIS etre presentes
    comme des leviers de negociation."""
    levers = semantic_levers["negotiation_levers"]
    blob = " ".join(levers).casefold()
    fautifs = [tok for tok in _ATOUT_TOKENS if tok in blob]
    assert not fautifs, (
        f"Des atouts ont fui dans les leviers ({fautifs}) : {levers}"
    )
