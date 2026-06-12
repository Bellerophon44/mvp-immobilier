"""Tests-first (phase A) du fix de l'issue #80 — extraction `single_storey`,
filtre deterministe copropriete, prompt et isolation.

Couvre les AC14-AC25 de docs/specs/fix-issue-80-SPEC.md (§5.3, §5.4).
Regle absolue (lecon 9.10, spec §3.4) : on mocke
`llm_semantic.client.chat.completions.create` — la VRAIE dependance, qui
renvoie un JSON controle ou leve — JAMAIS la facade `analyze_semantic` (et on
ne recopie pas le filtre dans le test : l'oracle observe la sortie de
`analyze_semantic`, le point exact ou la spec place le filtre, avant cache).

Textes d'annonce SYNTHETIQUES uniquement (repo public, CONTEXT §11.3), un
texte UNIQUE par appel pour maitriser la cle de cache (hash du texte).
L'isolation inter-tests du cache module `llm_semantic._CACHE` est assuree par
la fixture autouse de conftest.py (AC25, lecon 9.9 : jamais en fixture
locale).

AC DIFFERES AU PUSH 2 — hors perimetre de la phase verte initiale (ne PAS les
implementer au push 1) : AC26-AC33 (retrait des 3 marqueurs xfail, bascule
des 5 oracles de tests/test_evals_harness.py, suite complete verte) et
AC34-AC35 (docs). AC36-AC39 (evals payantes) : portes par backend/evals/,
intouche en phase A (les xfail existants sont la preuve de reproduction).
"""

import ast
import json
import pathlib

import pytest

import app.llm_semantic as llm


# ---------------------------------------------------------------------------
# Mock du client OpenAI reel (pattern test_photo_evidence / events_hardening)
# ---------------------------------------------------------------------------

class _MockCreate:
    """Mock appelable de client.chat.completions.create : compte les appels,
    renvoie un contenu JSON configurable (`content`) ou leve (`exc`)."""

    def __init__(self, content="{}", exc=None):
        self.content = content
        self.exc = exc
        self.call_count = 0

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        if self.exc is not None:
            raise self.exc

        class _Msg:
            pass

        msg = _Msg()
        msg.content = self.content
        choice = type("_Choice", (), {"message": msg})()
        return type("_Resp", (), {"choices": [choice]})()


@pytest.fixture()
def mock_llm(monkeypatch):
    mock = _MockCreate()
    monkeypatch.setattr(llm.client.chat.completions, "create", mock)
    return mock


def _payload(listing_overrides=None, questions=None, levers=None,
             drop_listing_keys=()):
    """JSON de reponse LLM controle, complet au format du prompt."""
    listing = {
        "city": "Metz",
        "district": None,
        "property_type": "maison",
        "surface_m2": 120,
        "price_total": 300000,
        "dpe": "C",
        "construction_year": 2005,
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
    listing.update(listing_overrides or {})
    for key in drop_listing_keys:
        listing.pop(key, None)
    return json.dumps(
        {
            "transparency_score": 70,
            "verdict": "Bonne",
            "risk_level": "Faible",
            "summary": "ok",
            "risk_summary": "ok",
            "questions": questions if questions is not None else [],
            "negotiation_levers": levers if levers is not None else [],
            "local_claims": [],
            "listing": listing,
        },
        ensure_ascii=False,
    )


# Listes mockees de l'AC16 (chaines generiques inventees, spec §8).
_QUESTIONS_AC16 = [
    "Quel est le montant des charges de copropriété ?",
    "Y a-t-il un syndic ?",
    "Quelle est l'exposition ?",
]
_LEVERS_AC16 = ["Copropriété sans travaux votés", "DPE C"]


# ===========================================================================
# §5.3 — extraction single_storey (AC14, AC15)
# ===========================================================================

def test_ac14_coercition_single_storey_true_str_absent(mock_llm):
    """AC14 : true -> True ; "oui" (str) -> None ; cle absente -> None.
    (+ borne false -> False, meme convention que has_elevator)."""
    mock_llm.content = _payload({"single_storey": True})
    out = llm.analyze_semantic("maison synthetique fix80 ac14 cas true jardin")
    assert out["listing"]["single_storey"] is True

    mock_llm.content = _payload({"single_storey": False})
    out = llm.analyze_semantic("maison synthetique fix80 ac14 cas false garage")
    assert out["listing"]["single_storey"] is False

    mock_llm.content = _payload({"single_storey": "oui"})
    out = llm.analyze_semantic("maison synthetique fix80 ac14 cas str cellier")
    assert out["listing"]["single_storey"] is None

    mock_llm.content = _payload(drop_listing_keys=("single_storey",))
    out = llm.analyze_semantic("maison synthetique fix80 ac14 cas absent verger")
    assert out["listing"]["single_storey"] is None


def test_ac15_fallback_chemin_reel_single_storey_none_contrat_intact(mock_llm):
    """AC15 : le client LEVE (chemin reel du fallback, lecon 9.10) -> la
    sortie porte listing["single_storey"] is None et le contrat fallback
    existant est intact (marqueur _fallback, listes vides)."""
    mock_llm.exc = RuntimeError("panne OpenAI simulee fix80 ac15")
    out = llm.analyze_semantic("maison synthetique fix80 ac15 panne potager")
    assert out["listing"]["single_storey"] is None
    assert out.get("_fallback") is True
    assert out["questions"] == []
    assert out["negotiation_levers"] == []
    assert out["listing"]["property_type"] is None


# ===========================================================================
# §5.3 — filtre deterministe copropriete (AC16-AC22)
# ===========================================================================

def test_ac16_filtre_maison_retire_copropriete_des_deux_listes(mock_llm):
    """AC16 : maison + texte sans copropri/syndic + condo_fees null -> les
    items copropri/syndic sont retires de questions ET de negotiation_levers,
    ordre des items conserves preserve."""
    mock_llm.content = _payload(
        questions=_QUESTIONS_AC16, levers=_LEVERS_AC16
    )
    out = llm.analyze_semantic(
        "maison individuelle synthetique fix80 ac16 jardin clos garage double"
    )
    assert out["questions"] == ["Quelle est l'exposition ?"]
    assert out["negotiation_levers"] == ["DPE C"]


def test_ac17_filtre_insensible_a_la_casse(mock_llm):
    """AC17 : « COPROPRIÉTÉ » et « Syndic » sont retires (casefold)."""
    mock_llm.content = _payload(
        questions=[
            "Le règlement de COPROPRIÉTÉ est-il disponible ?",
            "Le Syndic a-t-il vote des travaux ?",
            "Quelle est l'orientation du séjour ?",
        ],
        levers=["SYNDIC bénévole", "Toiture récente"],
    )
    out = llm.analyze_semantic(
        "maison individuelle synthetique fix80 ac17 plein sud terrain plat"
    )
    assert out["questions"] == ["Quelle est l'orientation du séjour ?"]
    assert out["negotiation_levers"] == ["Toiture récente"]


def test_ac18_cache_porte_la_valeur_filtree_un_seul_appel(mock_llm):
    """AC18 : la valeur mise en cache est la valeur FILTREE — un second appel
    sur le meme texte renvoie le resultat filtre avec mock.call_count == 1
    (cache hit). Pre-condition : cache vide en entree de test (preuve que le
    reset autouse de conftest opere, AC25)."""
    assert llm._CACHE == {}, (
        "cache non vide en entree de test : le reset autouse de conftest "
        "(AC25) n'opere pas"
    )
    mock_llm.content = _payload(questions=_QUESTIONS_AC16, levers=_LEVERS_AC16)
    texte = "maison individuelle synthetique fix80 ac18 cache hit veranda"
    out1 = llm.analyze_semantic(texte)
    out2 = llm.analyze_semantic(texte)
    assert mock_llm.call_count == 1, "second appel attendu en cache hit"
    assert out1["questions"] == ["Quelle est l'exposition ?"]
    assert out2["questions"] == ["Quelle est l'exposition ?"]
    assert out2["negotiation_levers"] == ["DPE C"]


def test_ac19_appartement_aucun_item_retire(mock_llm):
    """AC19 (garde, verte des la phase A) : appartement, memes listes mockees
    -> aucune question ni levier retire."""
    mock_llm.content = _payload(
        {"property_type": "appartement"},
        questions=_QUESTIONS_AC16,
        levers=_LEVERS_AC16,
    )
    out = llm.analyze_semantic(
        "appartement synthetique fix80 ac19 balcon lumineux centre"
    )
    assert out["questions"] == _QUESTIONS_AC16
    assert out["negotiation_levers"] == _LEVERS_AC16


def test_ac20_maison_texte_mentionnant_copropriete_aucun_filtrage(mock_llm):
    """AC20 (garde, verte des la phase A) : maison mais le texte d'annonce
    mentionne lui-meme la copropriete (horizontale) -> question legitime,
    aucun item retire."""
    mock_llm.content = _payload(questions=_QUESTIONS_AC16, levers=_LEVERS_AC16)
    out = llm.analyze_semantic(
        "maison synthetique fix80 ac20 en copropriété horizontale de lotissement"
    )
    assert out["questions"] == _QUESTIONS_AC16
    assert out["negotiation_levers"] == _LEVERS_AC16


def test_ac21_maison_condo_fees_non_null_aucun_filtrage(mock_llm):
    """AC21 (garde, verte des la phase A) : condo_fees non null dans la
    reponse mockee (preuve de copropriete) -> aucun item retire."""
    mock_llm.content = _payload(
        {"condo_fees": 1200},
        questions=_QUESTIONS_AC16,
        levers=_LEVERS_AC16,
    )
    out = llm.analyze_semantic(
        "maison synthetique fix80 ac21 charges annuelles terrain commun"
    )
    assert out["questions"] == _QUESTIONS_AC16
    assert out["negotiation_levers"] == _LEVERS_AC16


def test_ac22_property_type_null_aucun_filtrage(mock_llm):
    """AC22 (garde, verte des la phase A) : property_type null dans la
    reponse mockee -> conservateur, aucun item retire."""
    mock_llm.content = _payload(
        {"property_type": None},
        questions=_QUESTIONS_AC16,
        levers=_LEVERS_AC16,
    )
    out = llm.analyze_semantic(
        "bien synthetique fix80 ac22 type inconnu grand sejour"
    )
    assert out["questions"] == _QUESTIONS_AC16
    assert out["negotiation_levers"] == _LEVERS_AC16


# ===========================================================================
# §5.4 — prompt, fallback, isolation (AC23-AC25)
# ===========================================================================

def _regles_du_prompt():
    """Decoupe la section `Règles :` du template en regles individuelles
    (delimiteur `\n- `, tolere les regles ecrites sur plusieurs lignes)."""
    _, _, regles = llm.USER_PROMPT_TEMPLATE.partition("Règles :")
    assert regles, "section `Règles :` absente du USER_PROMPT_TEMPLATE"
    return ["- " + chunk for chunk in regles.split("\n- ")[1:]]


def test_ac23_prompt_format_regle_et_fallback_single_storey():
    """AC23 : le format `listing` du prompt declare single_storey ; une regle
    enonce « true UNIQUEMENT si plain-pied explicitement affirme, jamais
    deduit d'une mention de rez-de-chaussee, sinon null » ;
    _FALLBACK["listing"] porte single_storey: None."""
    format_bloc = llm.USER_PROMPT_TEMPLATE.partition("Règles :")[0]
    assert '"single_storey"' in format_bloc, (
        "single_storey absent du format JSON du bloc listing"
    )

    regles = [r for r in _regles_du_prompt() if "single_storey" in r]
    assert regles, "regle single_storey absente de la section Règles"
    corpus = " ".join(regles).casefold()
    assert "plain-pied" in corpus, "la regle doit citer le plain-pied explicite"
    assert "rez-de-chaussée" in corpus, (
        "la regle doit interdire la deduction depuis une mention de "
        "rez-de-chaussée"
    )
    assert "null" in corpus, "la regle doit prescrire null par defaut"

    assert llm._FALLBACK["listing"]["single_storey"] is None


def test_ac24_regle_questions_conditionnee_au_type_de_bien():
    """AC24 (part automatisable) : une regle du prompt conditionne les sujets
    copropriete/syndic au type de bien (mention conjointe copropri + maison),
    SANS retirer « copropriété » de la liste d'exemples de la regle
    `questions` (les appartements en ont besoin)."""
    regles = _regles_du_prompt()
    regles_questions = [r for r in regles if "`questions`" in r]
    assert regles_questions, "regle `questions` absente du prompt"
    assert any("copropriété" in r for r in regles_questions), (
        "« copropriété » doit RESTER dans les exemples de la regle questions"
    )
    assert any(
        "copropri" in r.casefold() and "maison" in r.casefold() for r in regles
    ), (
        "aucune regle ne conditionne les sujets copropriete/syndic au type de "
        "bien (jamais pour une maison individuelle)"
    )


def test_ac24_system_prompt_inchange():
    """AC24 (garde, verte des la phase A) : SYSTEM_PROMPT fige a la lettre —
    le fix ne doit pas le toucher (spec §3.3)."""
    assert llm.SYSTEM_PROMPT == (
        "Tu es un assistant spécialisé en analyse d'annonces immobilières "
        "françaises. Ton rôle n'est PAS d'estimer un prix. "
        "Tu dois analyser la qualité de l'information, les risques, "
        "et extraire les données structurées observables dans l'annonce. "
        "Tu es prudent, neutre, explicable et factuel. Tu n'inventes pas."
    )


def test_ac25_conftest_reset_autouse_cache_llm_semantic():
    """AC25 (statique) : tests/conftest.py definit une fixture AUTOUSE qui
    vide llm_semantic._CACHE avant chaque test (lecon 9.9 : reset d'etat
    partage de module en conftest global, jamais en fixture locale). Le volet
    dynamique est porte par la pre-condition `_CACHE == {}` de l'AC18."""
    src = (pathlib.Path(__file__).parent / "conftest.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(src)
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        decos = " ".join(
            ast.get_source_segment(src, d) or "" for d in node.decorator_list
        )
        body = ast.get_source_segment(src, node) or ""
        if (
            "fixture" in decos
            and "autouse=True" in decos
            and "llm_semantic" in body
            and "_CACHE.clear" in body
        ):
            candidates.append(node.name)
    assert candidates, (
        "fixture autouse vidant llm_semantic._CACHE absente de "
        "tests/conftest.py (AC25, lecon 9.9)"
    )
