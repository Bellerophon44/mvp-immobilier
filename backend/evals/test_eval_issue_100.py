"""Cas d'evaluation de l'issue #100 (retour-pilote, gravite/bloquant-credibilite).

Volet C5 : pour un appartement dont l'annonce DONNE le montant des charges
(« Charges de copropriete : 220 € par mois »), l'analyse posait quand meme une
question demandant le MONTANT des charges, en contradiction avec la question
deterministe (`analysis._amenity_actions`) qui CITE ce montant. L'annonce de
cases/issue_100.txt est SYNTHETIQUE : reecriture entierement fictive reproduisant
le declencheur (copropriete + charges chiffrees explicites), jamais d'extrait
reel d'annonce versionne (CONTEXT §11.3, repo public).

Un seul appel LLM reel par run (fixture module-scoped) : cout borne a 1 appel par
cas (spec §3.4), toutes les assertions consomment ce resultat. Sanity
d'extraction bloquantes (§5.2) ; la regression C5 est BLOQUANTE depuis le fix
(filtre deterministe `_filter_redundant_fee_question` + regle de prompt, chantier
issue #100 / C5).
"""

import pytest

from app.llm_semantic import analyze_semantic


@pytest.fixture(scope="module")
def semantic_issue_100(load_case):
    # SEUL point d'appel du LLM de ce module (AC14 : 1 appel par cas et par run).
    return analyze_semantic(load_case("issue_100"))


# ---------------------------------------------------------------------------
# Sanity d'extraction (§5.2) — bloquantes, sans xfail.
# ---------------------------------------------------------------------------

def test_extraction_city_metz(semantic_issue_100):
    city = (semantic_issue_100["listing"]["city"] or "").strip().casefold()
    assert city.startswith("metz")


def test_extraction_property_type_appartement(semantic_issue_100):
    assert semantic_issue_100["listing"]["property_type"] == "appartement"


def test_extraction_surface(semantic_issue_100):
    assert semantic_issue_100["listing"]["surface_m2"] == 92.0


def test_extraction_price_total(semantic_issue_100):
    assert semantic_issue_100["listing"]["price_total"] == 245000.0


def test_extraction_condo_fees_present(semantic_issue_100):
    # Le montant des charges est explicite dans l'annonce -> condo_fees doit etre
    # extrait : c'est la PRECONDITION du filtre C5 (_filter_redundant_fee_question
    # n'agit que si condo_fees is not None). Si None, le filtre ne pourrait pas
    # operer et la regression ci-dessous serait verte par accident.
    assert semantic_issue_100["listing"]["condo_fees"] is not None


def test_questions_non_vides(semantic_issue_100):
    # Garantit que la regression C5 n'est pas verte par vacuite.
    assert len(semantic_issue_100["questions"]) >= 1


# ---------------------------------------------------------------------------
# Regression C5 (issue #100) — bloquante depuis le fix.
# ---------------------------------------------------------------------------

def test_regression_c5_aucune_question_ne_redemande_le_montant_des_charges(
    semantic_issue_100,
):
    """Aucune question ne doit demander le MONTANT des charges : il est donne
    dans l'annonce. Les questions sur ce que COUVRENT les charges ou sur leur
    evolution restent legitimes (non visees ici)."""
    fautives = [
        q
        for q in semantic_issue_100["questions"]
        if "charge" in str(q).casefold()
        and any(t in str(q).casefold() for t in ("montant", "combien", "coût", "cout"))
    ]
    assert not fautives, (
        f"Questions redemandant le montant des charges (deja donne) : {fautives}"
    )
