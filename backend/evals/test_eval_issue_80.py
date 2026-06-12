"""Cas d'evaluation de l'issue #80 (retour-pilote, gravite/bloquant-credibilite).

Symptomes constates sur une villa de plain-pied : (1) le pilier prix rend
« rez-de-chaussée » pour une maison de plain-pied ; (2) le LLM pose une question
de copropriete sur une maison individuelle. L'annonce de cases/issue_80.txt est
SYNTHETIQUE : reecriture entierement fictive reproduisant les declencheurs,
jamais d'extrait reel d'annonce versionne (CONTEXT §11.3, repo public).

Un seul appel LLM reel par run (fixture module-scoped). Assertions de sanity
bloquantes sur l'extraction (§5.2) ; regressions connues en xfail strict=False
(§5.3), a retirer au chantier fix.
"""

import pytest

from app.analysis import _amenity_attrs
from app.llm_semantic import analyze_semantic
from app.market_stats import _criteria_signal
from scrapers.base import construction_epoch


@pytest.fixture(scope="module")
def semantic_issue_80(load_case):
    # SEUL point d'appel du LLM dans evals/ : cout borne a 1 appel par run
    # (spec §3.4/AC14), toutes les assertions consomment ce resultat.
    return analyze_semantic(load_case("issue_80"))


# ---------------------------------------------------------------------------
# Sanity d'extraction (§5.2) — bloquantes, sans xfail : une PR de prompt qui
# casse l'un de ces champs met le job evals au rouge.
# ---------------------------------------------------------------------------

def test_extraction_property_type_maison(semantic_issue_80):
    assert semantic_issue_80["listing"]["property_type"] == "maison"


def test_extraction_surface(semantic_issue_80):
    assert semantic_issue_80["listing"]["surface_m2"] == 282.0


def test_extraction_dpe(semantic_issue_80):
    assert semantic_issue_80["listing"]["dpe"] == "C"


def test_extraction_construction_year(semantic_issue_80):
    assert semantic_issue_80["listing"]["construction_year"] == 2006


def test_extraction_price_total(semantic_issue_80):
    assert semantic_issue_80["listing"]["price_total"] == 565000.0


def test_extraction_single_storey(semantic_issue_80):
    # AC37 (chantier fix #80) : le texte synthetique affirme litteralement
    # « plain-pied » — meme classe de fiabilite que property_type, donc
    # bloquant sans xfail.
    assert semantic_issue_80["listing"]["single_storey"] is True


def test_questions_non_vides(semantic_issue_80):
    # Garantit que la regression B (mots interdits dans `questions`) n'est pas
    # verte par vacuite.
    assert len(semantic_issue_80["questions"]) >= 1


# ---------------------------------------------------------------------------
# Regressions connues (§5.3) — xfail strict=False (LLM non deterministe : un
# run ou le bug ne se manifeste pas produit un XPASS qui ne doit pas mettre la
# CI au rouge). Retrait des marqueurs = checklist du chantier fix.
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False, reason="issue #80, fix non livre")
def test_regression_a_rendu_sans_rez_de_chaussee(semantic_issue_80):
    """Invariant visible utilisateur, agnostique du fix retenu : pour une
    maison de plain-pied, le signal du pilier prix compose a partir de
    l'extraction REELLE ne contient pas « rez-de-chaussée ». Aucune assertion
    sur la valeur extraite de floor (design du fix non fige), aucun appel LLM
    supplementaire (reutilise la fixture)."""
    listing = semantic_issue_80["listing"]
    attrs = _amenity_attrs(listing)
    signal = _criteria_signal(
        listing["dpe"],
        construction_epoch(listing["construction_year"]),
        {},
        attrs,
    )
    assert "rez-de-chaussée" not in signal


@pytest.mark.xfail(strict=False, reason="issue #80, fix non livre")
def test_regression_b_questions_sans_copropriete(semantic_issue_80):
    """Maison individuelle : aucune question generee ne doit mentionner la
    copropriete ou le syndic (le texte synthetique n'en parle pas, AC13 : le
    symptome vient du LLM)."""
    interdits = ("copropriété", "copropriete", "syndic")
    fautives = [
        q for q in semantic_issue_80["questions"]
        if any(token in q.casefold() for token in interdits)
    ]
    assert not fautives, f"Questions copropriete/syndic sur maison individuelle : {fautives}"
