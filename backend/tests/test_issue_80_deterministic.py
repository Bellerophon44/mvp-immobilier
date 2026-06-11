"""Tests deterministes gratuits du cas issue #80 (spec evals-harness §6).

Sans LLM, sans reseau, sans cle reelle : couche rendu
(market_stats._amenity_phrases / _criteria_signal) et generateur deterministe
de questions (analysis._amenity_actions). La regression connue
« rez-de-chaussée » est en xfail(strict=True) : memoire executable — le jour
du fix, le XPASS casse la suite et force le retrait du marqueur.

Note pour le chantier fix : si la signature de _criteria_signal ou de
_amenity_phrases change (ex. ajout de property_type), mettre a jour ces tests
ET l'assertion de regression A de evals/test_eval_issue_80.py dans le meme
mini-cycle.
"""

import pytest

from app.analysis import _amenity_actions, _amenity_attrs
from app.market_stats import _criteria_signal


@pytest.mark.xfail(strict=True, reason="issue #80, fix non livre")
def test_signal_maison_plain_pied_sans_rez_de_chaussee():
    """Une maison de plain-pied (floor=0) ne doit pas etre rendue
    « rez-de-chaussée » dans le signal du pilier prix. Structurellement rouge
    aujourd'hui : analysis._AMENITY_KEYS ne transmet pas property_type et
    _amenity_phrases rend floor == 0 inconditionnellement."""
    listing = {
        "property_type": "maison",
        "floor": 0,
        "has_elevator": None,
        "has_terrace": True,
        "has_balcony": None,
        "has_cellar": None,
        "parking": None,
        "bedrooms": 5,
        "condo_fees": None,
    }
    attrs = _amenity_attrs(listing)
    signal = _criteria_signal(None, None, {}, attrs)
    assert "rez-de-chaussée" not in signal


def test_amenity_actions_maison_sans_condo_fees_sans_question_copropriete():
    """Garde passante : fige le fait que le symptome 2 de #80 (question
    copropriete sur maison individuelle) vient du LLM, pas du generateur
    deterministe."""
    listing = {
        "property_type": "maison",
        "floor": 0,
        "has_elevator": None,
        "has_terrace": True,
        "has_balcony": None,
        "has_cellar": None,
        "parking": None,
        "bedrooms": 5,
        "condo_fees": None,
    }
    actions = _amenity_actions(listing)
    fautives = [
        item
        for item in actions["questions"] + actions["negotiation"]
        if "copropri" in item.casefold() or "syndic" in item.casefold()
    ]
    assert not fautives, f"Questions copropriete/syndic inattendues : {fautives}"
