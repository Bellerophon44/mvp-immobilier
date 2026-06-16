"""Tests du fix C5 (issue #100, retour-pilote, gravite/bloquant-credibilite).

Symptome constate : pour un appartement dont l'annonce DONNE les charges
(« Charges mensuelles : 320 € »), l'analyse posait quand meme « Quel est le
montant des charges de copropriete ? » (LLM), pendant que la question
deterministe (`analysis._amenity_actions`) CITE ce montant -> on demande une
info qu'on affiche par ailleurs : incoherence visible.

Cause racine : aucun invariant « ne pas redemander ce que l'annonce fournit
deja ». Fix : filtre deterministe `_filter_redundant_fee_question` dans
`analyze_semantic` (retire les questions LLM sur le MONTANT des charges quand
`condo_fees` est extrait) + regle de prompt generale.

Regle absolue (lecon 9.10, comme test_issue_80_semantic_filter) : on mocke
`llm_semantic.client.chat.completions.create` — la VRAIE dependance — JAMAIS la
facade `analyze_semantic` ; l'oracle observe la sortie de `analyze_semantic`, au
point exact ou le filtre est pose, avant cache. Listings SYNTHETIQUES (repo
public, CONTEXT §11.3). Un texte UNIQUE par appel (cle de cache = hash texte) ;
l'isolation du cache module est assuree par la fixture autouse de conftest.py
(lecon 9.9).
"""

import ast
import json
import pathlib

import pytest

import app.llm_semantic as llm
from app.analysis import _amenity_actions


class _MockCreate:
    """Mock appelable de client.chat.completions.create (pattern issue #80)."""

    def __init__(self, content="{}", exc=None):
        self.content = content
        self.exc = exc
        self.call_count = 0

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        if self.exc is not None:
            raise self.exc
        msg = type("_Msg", (), {"content": self.content})()
        choice = type("_Choice", (), {"message": msg})()
        return type("_Resp", (), {"choices": [choice]})()


@pytest.fixture()
def mock_llm(monkeypatch):
    mock = _MockCreate()
    monkeypatch.setattr(llm.client.chat.completions, "create", mock)
    return mock


def _payload(listing_overrides=None, questions=None):
    """JSON de reponse LLM controle, appartement en copropriete par defaut."""
    listing = {
        "city": "Metz",
        "district": None,
        "property_type": "appartement",
        "surface_m2": 195,
        "price_total": 389000,
        "dpe": "D",
        "construction_year": None,
        "floor": 3,
        "has_elevator": True,
        "has_terrace": None,
        "has_balcony": True,
        "has_cellar": True,
        "parking": None,
        "bedrooms": 3,
        "condo_fees": 3840,
        "single_storey": None,
    }
    listing.update(listing_overrides or {})
    return json.dumps(
        {
            "transparency_score": 70,
            "verdict": "Bonne",
            "risk_level": "Faible",
            "summary": "ok",
            "risk_summary": "ok",
            "questions": questions if questions is not None else [],
            "negotiation_levers": [],
            "local_claims": [],
            "listing": listing,
        },
        ensure_ascii=False,
    )


_Q_MONTANT = "Quel est le montant des charges de copropriété ?"
_Q_COUVERTURE = "Que couvrent exactement les charges de copropriété ?"
_Q_EXPO = "Quelle est l'exposition de l'appartement ?"


def test_montant_charges_retire_quand_condo_fees_connu(mock_llm):
    """Coeur du fix : condo_fees extrait + question LLM sur le montant des
    charges -> la question est retiree ; les autres sont conservees, ordre
    preserve."""
    mock_llm.content = _payload(questions=[_Q_MONTANT, _Q_EXPO])
    out = llm.analyze_semantic(
        "appartement synthetique issue100 montant charges balcon cave"
    )
    assert out["questions"] == [_Q_EXPO]


def test_question_couverture_charges_conservee(mock_llm):
    """Garde : une question sur ce que COUVRENT les charges (sans demander le
    montant) reste legitime meme quand condo_fees est connu."""
    mock_llm.content = _payload(questions=[_Q_COUVERTURE, _Q_EXPO])
    out = llm.analyze_semantic(
        "appartement synthetique issue100 couverture charges ascenseur"
    )
    assert out["questions"] == [_Q_COUVERTURE, _Q_EXPO]


def test_combien_charges_retire(mock_llm):
    """Variante de formulation : « À combien s'elevent les charges ? » est aussi
    une demande de montant -> retiree."""
    mock_llm.content = _payload(
        questions=["À combien s'élèvent les charges mensuelles ?", _Q_EXPO]
    )
    out = llm.analyze_semantic(
        "appartement synthetique issue100 combien charges troisieme etage"
    )
    assert out["questions"] == [_Q_EXPO]


def test_condo_fees_null_aucun_filtrage(mock_llm):
    """Garde conservatrice : si condo_fees n'est PAS extrait (montant non
    acquis), on ne retire rien — demander le montant est alors legitime."""
    mock_llm.content = _payload(
        {"condo_fees": None}, questions=[_Q_MONTANT, _Q_EXPO]
    )
    out = llm.analyze_semantic(
        "appartement synthetique issue100 charges inconnues lumineux"
    )
    assert out["questions"] == [_Q_MONTANT, _Q_EXPO]


def test_questions_non_liste_renvoyees_telles_quelles(mock_llm):
    """Robustesse (lecon issue #80) : si le LLM renvoie `questions` en CHAINE,
    le filtre ne l'eclate pas en caracteres (garde isinstance)."""
    mock_llm.content = _payload(questions=_Q_MONTANT)
    out = llm.analyze_semantic(
        "appartement synthetique issue100 chaine adverse cellier"
    )
    assert out["questions"] == _Q_MONTANT


def test_filtre_items_non_str_sans_typeerror(mock_llm):
    """Robustesse : un item non-chaine est converti via str() avant test, pas
    de TypeError ; un item portant « charges »+« montant » sous forme d'objet
    est retire, un nombre est conserve."""
    mock_llm.content = _payload(
        questions=[{"q": "montant des charges ?"}, 42, _Q_EXPO]
    )
    out = llm.analyze_semantic(
        "appartement synthetique issue100 items non str balcon"
    )
    assert out["questions"] == [42, _Q_EXPO]


def test_cache_porte_la_valeur_filtree_un_seul_appel(mock_llm):
    """La valeur mise en cache est la valeur FILTREE (filtre applique avant
    cache) ; second appel sur le meme texte = cache hit (call_count == 1)."""
    assert llm._CACHE == {}, "reset autouse de conftest inoperant (lecon 9.9)"
    mock_llm.content = _payload(questions=[_Q_MONTANT, _Q_EXPO])
    texte = "appartement synthetique issue100 cache hit charges balcon cave"
    out1 = llm.analyze_semantic(texte)
    out2 = llm.analyze_semantic(texte)
    assert mock_llm.call_count == 1
    assert out1["questions"] == [_Q_EXPO]
    assert out2["questions"] == [_Q_EXPO]


def test_question_canonique_charges_toujours_emise(mock_llm):
    """Cote deterministe : apres avoir retire la question LLM redondante, la
    question canonique unique sur les charges (que couvrent, montant cite) est
    toujours produite par _amenity_actions -> l'utilisateur garde UNE question
    coherente sur les charges, pas zero."""
    extra = _amenity_actions({"condo_fees": 3840, "property_type": "appartement"})
    charges_q = [q for q in extra["questions"] if "charges" in q.casefold()]
    assert len(charges_q) == 1
    assert "3840" in charges_q[0]


def test_regle_prompt_interdit_redemander_info_explicite():
    """Statique : une regle du prompt interdit de poser une question dont la
    reponse est explicite dans l'annonce, en citant le montant des charges,
    SANS retirer « copropriété » des exemples de la regle questions (lecon
    AC24 issue #80 : les appartements en ont besoin)."""
    _, _, regles = llm.USER_PROMPT_TEMPLATE.partition("Règles :")
    assert regles, "section `Règles :` absente du USER_PROMPT_TEMPLATE"
    corpus = regles.casefold()
    assert "explicitement" in corpus, (
        "aucune regle n'interdit de redemander une info explicite de l'annonce"
    )
    assert "montant des charges" in corpus, (
        "la regle doit citer le cas du montant des charges"
    )
    assert "copropriété" in corpus, (
        "« copropriété » doit RESTER dans les exemples (lecon AC24 issue #80)"
    )
