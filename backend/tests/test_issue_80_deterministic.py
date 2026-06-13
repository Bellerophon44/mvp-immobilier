"""Tests deterministes gratuits du cas issue #80 (specs evals-harness §6 et
fix-issue-80 §5.1/§5.2).

Sans LLM, sans reseau, sans cle reelle : couche rendu
(market_stats._amenity_phrases / _criteria_signal) et generateur deterministe
de questions (analysis._amenity_actions).

Fix livre (chantier fix-issue-80, push 2) : la regression « rez-de-chaussée »
est BLOQUANTE — le marqueur xfail(strict=True) a ete retire apres son XPASS
au push 1, comme prevu. Les tests AC1-AC13 (+ durcissements phase B), livres
au push 1 dans tests/test_fix_issue_80_deterministic.py pour ne pas casser
l'oracle du harnais qui execute CE fichier en sous-processus (lecon du
2026-06-12), sont replies ici au push 2, conformement au placement prescrit
par la spec §5.1 — ce fichier doit rester integralement vert : l'oracle
test_evals_harness.py::test_ac19_ac20_ac21_statuts_reels_bloquants_et_passants
exige returncode 0 sans xfailed/xpassed/failed.

Tous les listings sont SYNTHETIQUES (repo public, CONTEXT §11.3).
"""

from app.analysis import _AMENITY_KEYS, _amenity_actions, _amenity_attrs
from app.market_stats import _criteria_signal


def _listing(**overrides):
    """Listing synthetique minimal au format de sortie de llm_semantic."""
    base = {
        "property_type": None,
        "floor": None,
        "has_elevator": None,
        "has_terrace": None,
        "has_balcony": None,
        "has_cellar": None,
        "parking": None,
        "bedrooms": None,
        "condo_fees": None,
        "single_storey": None,
    }
    base.update(overrides)
    return base


def _signal(listing):
    return _criteria_signal(None, None, {}, _amenity_attrs(listing))


# ===========================================================================
# Tests historiques du harnais (evals-harness §6) — corps inchanges
# ===========================================================================

def test_signal_maison_plain_pied_sans_rez_de_chaussee():
    """Une maison de plain-pied (floor=0) ne doit pas etre rendue
    « rez-de-chaussée » dans le signal du pilier prix. Ex-xfail strict=True
    (memoire executable du fix) : bloquant depuis le push 2 du chantier
    fix-issue-80."""
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


# ===========================================================================
# §5.1 — rendu deterministe (AC1-AC9 + lignes de la table de verite §4)
# ===========================================================================

def test_ac1_maison_floor_0_sans_cle_single_storey_sans_rez_de_chaussee():
    """AC1 : maison, floor=0, SANS cle single_storey dans le listing -> pas de
    « rez-de-chaussée ». Meme oracle que
    test_signal_maison_plain_pied_sans_rez_de_chaussee, variante sans la cle
    (robustesse au .get())."""
    listing = _listing(property_type="maison", floor=0, has_terrace=True, bedrooms=5)
    del listing["single_storey"]
    assert "rez-de-chaussée" not in _signal(listing)


def test_ac2_maison_floor_0_single_storey_none_aucune_mention_etage():
    """AC2 : maison, floor=0, single_storey=None, has_terrace=True -> ni
    rez-de-chaussée, ni etage, ni ascenseur, ni plain-pied ; les autres
    phrases (terrasse) survivent."""
    signal = _signal(_listing(property_type="maison", floor=0, has_terrace=True))
    assert "rez-de-chaussée" not in signal
    assert "étage" not in signal
    assert "ascenseur" not in signal
    assert "plain-pied" not in signal
    assert "avec terrasse" in signal


def test_table_maison_floor_0_single_storey_false_aucune_mention():
    """Table §4 ligne 1 (variante False) : maison, floor=0,
    single_storey=False -> aucune mention etage/plain-pied."""
    signal = _signal(_listing(property_type="maison", floor=0, single_storey=False))
    assert "rez-de-chaussée" not in signal
    assert "plain-pied" not in signal
    assert "étage" not in signal


def test_ac3_maison_floor_none_single_storey_true_plain_pied():
    """AC3 : maison, floor=None, single_storey=True -> « de plain-pied »,
    sans etage / rez-de-chaussée / ascenseur."""
    signal = _signal(_listing(property_type="maison", single_storey=True))
    assert "de plain-pied" in signal
    assert "étage" not in signal
    assert "rez-de-chaussée" not in signal
    assert "ascenseur" not in signal


def test_ac4_maison_floor_0_single_storey_true_plain_pied():
    """AC4 : maison, floor=0, single_storey=True -> « de plain-pied »."""
    signal = _signal(_listing(property_type="maison", floor=0, single_storey=True))
    assert "de plain-pied" in signal


def test_ac5_maison_floor_2_single_storey_true_contradiction_omission():
    """AC5 : maison, floor=2, single_storey=True -> contradiction : ni
    plain-pied, ni « 2e étage », ni ascenseur (prudence, jamais « de
    plain-pied » pour une maison a etage)."""
    signal = _signal(_listing(property_type="maison", floor=2, single_storey=True))
    assert "plain-pied" not in signal
    assert "2e étage" not in signal
    assert "ascenseur" not in signal


def test_ac6_maison_floor_3_sans_ascenseur_bloc_entier_neutralise():
    """AC6 : maison, floor=3, has_elevator=False, single_storey=None -> ni
    « 3e étage » ni « sans ascenseur » (neutralisation du bloc complet, pas du
    seul floor=0)."""
    signal = _signal(
        _listing(property_type="maison", floor=3, has_elevator=False)
    )
    assert "3e étage" not in signal
    assert "sans ascenseur" not in signal


def test_table_maison_floor_none_sans_ascenseur_aucune_mention():
    """Table §4 ligne 6 : maison, floor=None, has_elevator=False,
    single_storey=None -> aucune mention (la branche « sans ascenseur » seule
    est neutralisee aussi pour une maison)."""
    signal = _signal(_listing(property_type="maison", has_elevator=False))
    assert "sans ascenseur" not in signal
    assert "ascenseur" not in signal


def test_ac7_appartement_rendu_etage_inchange():
    """AC7 (non-regression) : appartement, floor=0 -> « rez-de-chaussée » ;
    appartement, floor=4 sans ascenseur -> « 4e étage sans ascenseur »."""
    signal_rdc = _signal(_listing(property_type="appartement", floor=0))
    assert "rez-de-chaussée" in signal_rdc

    signal_4e = _signal(
        _listing(property_type="appartement", floor=4, has_elevator=False)
    )
    assert "4e étage sans ascenseur" in signal_4e


def test_ac8_appartement_single_storey_true_jamais_plain_pied():
    """AC8 (garde) : la mention « de plain-pied » est reservee aux maisons
    explicites — jamais pour un appartement, meme avec single_storey=True."""
    signal = _signal(_listing(property_type="appartement", single_storey=True))
    assert "plain-pied" not in signal


def test_ac9_property_type_null_floor_0_comportement_conserve():
    """AC9 (non-regression) : property_type null -> comportement actuel
    conserve (conservateur, §2) : « rez-de-chaussée » rendu pour floor=0."""
    signal = _signal(_listing(property_type=None, floor=0))
    assert "rez-de-chaussée" in signal


def test_table_property_type_null_single_storey_true_jamais_plain_pied():
    """Table §4 derniere ligne : property_type null + single_storey=True ->
    comportement actuel, jamais « plain-pied » (garde : personne ne rend
    plain-pied sans maison explicite)."""
    signal = _signal(_listing(property_type=None, single_storey=True, floor=0))
    assert "plain-pied" not in signal
    assert "rez-de-chaussée" in signal


# ===========================================================================
# Durcissement phase B (testeur) — bornes et valeurs adverses du rendu
# ===========================================================================

def test_b_table_maison_floor_1_single_storey_true_borne_contradiction():
    """Durcit AC5 : la garde contradiction est `floor >= 1` — floor=1 (borne
    basse) suffit a omettre plain-pied ET « 1er étage »."""
    signal = _signal(_listing(property_type="maison", floor=1, single_storey=True))
    assert "plain-pied" not in signal
    assert "étage" not in signal
    assert "rez-de-chaussée" not in signal


def test_b_appartement_floor_0_single_storey_true_rdc_sans_plain_pied():
    """Durcit AC7/AC8 (table §4 combinee) : appartement floor=0 reste
    « rez-de-chaussée » meme avec single_storey=True, jamais plain-pied."""
    signal = _signal(
        _listing(property_type="appartement", floor=0, single_storey=True)
    )
    assert "rez-de-chaussée" in signal
    assert "plain-pied" not in signal


def test_b_property_type_casse_variante_comportement_conservateur():
    """Durcit AC9 : « Maison » (casse variante) n'est pas « maison » explicite
    — egalite stricte (spec §2), comportement historique conserve (rendu
    rez-de-chaussée, pas de plain-pied). Limite documentee : la robustesse
    repose sur l'enum du prompt + la sanity d'eval property_type."""
    signal = _signal(
        _listing(property_type="Maison", floor=0, single_storey=True)
    )
    assert "rez-de-chaussée" in signal
    assert "plain-pied" not in signal


def test_b_single_storey_chaine_true_jamais_plain_pied():
    """Durcit AC3 : la preuve plain-pied est `is True` STRICT — une chaine
    truthy « true » ne rend jamais plain-pied."""
    signal = _signal(_listing(property_type="maison", single_storey="true"))
    assert "plain-pied" not in signal


def test_b_amenity_actions_property_type_null_etage_ascenseur_conserves():
    """Durcit AC10/AC11 : property_type null -> generateur deterministe
    inchange (conservateur, spec §2) : question ET levier etage/ascenseur
    produits."""
    actions = _amenity_actions(
        _listing(property_type=None, floor=4, has_elevator=False)
    )
    assert any(
        "étage" in q and "ascenseur" in q for q in actions["questions"]
    ), f"Question etage/ascenseur attendue pour type null : {actions['questions']}"
    assert any(
        "4e étage sans ascenseur" in lev for lev in actions["negotiation"]
    ), f"Levier etage/ascenseur attendu pour type null : {actions['negotiation']}"


# ===========================================================================
# §5.2 — actions deterministes (AC10-AC13)
# ===========================================================================

def test_ac10_amenity_actions_maison_jamais_etage_ascenseur():
    """AC10 : maison floor=5 sans ascenseur -> aucune question ni levier ne
    contient « étage » ou « ascenseur » (meme invariant que le rendu)."""
    actions = _amenity_actions(
        _listing(property_type="maison", floor=5, has_elevator=False)
    )
    fautives = [
        item
        for item in actions["questions"] + actions["negotiation"]
        if "étage" in str(item) or "ascenseur" in str(item)
    ]
    assert not fautives, f"Items etage/ascenseur produits pour une maison : {fautives}"


def test_ac11_amenity_actions_appartement_etage_ascenseur_presents():
    """AC11 (non-regression) : appartement floor=5 sans ascenseur -> question
    ET levier etage/ascenseur presents."""
    actions = _amenity_actions(
        _listing(property_type="appartement", floor=5, has_elevator=False)
    )
    assert any(
        "étage" in q and "ascenseur" in q for q in actions["questions"]
    ), f"Question etage/ascenseur attendue : {actions['questions']}"
    assert any(
        "5e étage sans ascenseur" in lev for lev in actions["negotiation"]
    ), f"Levier etage/ascenseur attendu : {actions['negotiation']}"


def test_ac12_amenity_actions_maison_condo_fees_question_charges_conservee():
    """AC12 (non-regression) : maison avec condo_fees=1200 -> la question
    charges de copropriete reste produite (copropriete horizontale prouvee
    par condo_fees — pas de sur-filtrage)."""
    actions = _amenity_actions(_listing(property_type="maison", condo_fees=1200))
    assert any(
        "copropri" in q.casefold() for q in actions["questions"]
    ), f"Question charges de copropriete attendue : {actions['questions']}"


def test_ac13_amenity_keys_transportent_property_type_et_single_storey():
    """AC13 : _AMENITY_KEYS contient property_type et single_storey, et
    _amenity_attrs les restitue."""
    assert "property_type" in _AMENITY_KEYS
    assert "single_storey" in _AMENITY_KEYS
    attrs = _amenity_attrs({"property_type": "maison", "single_storey": True})
    assert attrs.get("property_type") == "maison"
    assert attrs.get("single_storey") is True
