"""Tests deterministes (gratuits, sans LLM ni reseau) de la refonte des leviers
de negociation et de la nouvelle section « Atouts du bien ».

Objet : les leviers de negociation sont desormais cotes ACHETEUR (elements qui
pesent A LA BAISSE) et non plus les points forts du bien, lesquels alimentent une
section distincte `actions.highlights`. Cote backend deterministe, on couvre :
- `analysis._derived_negotiation_levers` : leviers derives de l'analyse elle-meme
  (prix sur-positionne, DPE faible, allegation locale peu plausible) ;
- le cablage dans `run_full_analysis` : `highlights` expose tel quel, leviers
  derives fusionnes (dedup) aux leviers LLM + confort.

Tous les listings sont SYNTHETIQUES (repo public, CONTEXT §11.3).
"""

import app.analysis as analysis
from app.analysis import _derived_negotiation_levers, run_full_analysis


# ===========================================================================
# _derived_negotiation_levers — fonction pure
# ===========================================================================

def test_prix_fortement_sur_positionne_donne_levier_principal():
    levers = _derived_negotiation_levers(
        {"verdict": "Fortement sur‑positionné"}, {}, None
    )
    assert any("nettement au-dessus" in lev for lev in levers)


def test_prix_legerement_sur_positionne_donne_levier():
    levers = _derived_negotiation_levers(
        {"verdict": "Légèrement sur‑positionné"}, {}, None
    )
    assert any("au-dessus de la fourchette" in lev for lev in levers)
    assert not any("nettement" in lev for lev in levers)


def test_prix_aligne_aucun_levier_prix():
    levers = _derived_negotiation_levers({"verdict": "Plutôt aligné"}, {}, None)
    assert not any("Prix au m²" in lev for lev in levers)


def test_prix_sous_positionne_jamais_levier_a_la_baisse():
    """Un bien sous-positionne est favorable a l'acheteur : pas un levier a la
    baisse. Garde le 'sur' de la detection insensible au tiret insecable."""
    levers = _derived_negotiation_levers(
        {"verdict": "Sous‑positionné"}, {}, None
    )
    assert not any("Prix au m²" in lev for lev in levers)


def test_prix_indetermine_aucun_levier():
    levers = _derived_negotiation_levers({"verdict": "Indéterminé"}, {}, None)
    assert levers == []


def test_dpe_g_donne_levier_passoire():
    levers = _derived_negotiation_levers(
        {"verdict": "Plutôt aligné"}, {"dpe": "G"}, None
    )
    assert any("DPE G" in lev and "passoire" in lev for lev in levers)


def test_dpe_f_donne_levier_passoire():
    levers = _derived_negotiation_levers(
        {"verdict": "Plutôt aligné"}, {"dpe": "F"}, None
    )
    assert any("DPE F" in lev for lev in levers)


def test_dpe_c_aucun_levier_dpe():
    levers = _derived_negotiation_levers(
        {"verdict": "Plutôt aligné"}, {"dpe": "C"}, None
    )
    assert not any("DPE" in lev for lev in levers)


def test_claim_peu_plausible_donne_levier():
    local_ctx = {
        "claims": [
            {"text": "vue cathédrale", "status": "peu_plausible", "note": "..."},
            {"text": "proche commerces", "status": "coherent", "note": "..."},
        ]
    }
    levers = _derived_negotiation_levers(
        {"verdict": "Plutôt aligné"}, {}, local_ctx
    )
    assert any("vue cathédrale" in lev for lev in levers)
    assert not any("proche commerces" in lev for lev in levers)


def test_ordre_stable_prix_puis_dpe_puis_allegation():
    local_ctx = {"claims": [{"text": "vue mer", "status": "peu_plausible", "note": ""}]}
    levers = _derived_negotiation_levers(
        {"verdict": "Fortement sur‑positionné"}, {"dpe": "G"}, local_ctx
    )
    assert len(levers) == 3
    assert "au m²" in levers[0]
    assert "DPE G" in levers[1]
    assert "vue mer" in levers[2]


def test_aucun_point_defavorable_liste_vide():
    """Bien aligne, bon DPE, aucune allegation douteuse -> aucun levier derive
    (on ne fabrique pas de levier pour remplir la section)."""
    local_ctx = {"claims": [{"text": "calme", "status": "coherent", "note": ""}]}
    levers = _derived_negotiation_levers(
        {"verdict": "Plutôt aligné"}, {"dpe": "B"}, local_ctx
    )
    assert levers == []


# ===========================================================================
# Cablage run_full_analysis — highlights expose, leviers derives fusionnes
# ===========================================================================

def _semantic_stub(**overrides):
    base = {
        "transparency_score": 70,
        "verdict": "Bonne",
        "risk_level": "Faible",
        "summary": "ok",
        "risk_summary": "ok",
        "questions": [],
        "highlights": ["Grand jardin arboré", "Garage double"],
        "negotiation_levers": [],
        "local_claims": [],
        "listing": {
            "city": "Metz", "district": None, "property_type": "maison",
            "surface_m2": 100.0, "price_total": 300000.0, "dpe": "G",
            "construction_year": 1955, "floor": None, "has_elevator": None,
            "has_terrace": None, "has_balcony": None, "has_cellar": None,
            "parking": None, "bedrooms": 4, "condo_fees": None,
            "single_storey": None,
        },
    }
    base.update(overrides)
    return base


def test_highlights_exposes_tels_quels_dans_actions(monkeypatch):
    monkeypatch.setattr(analysis, "analyze_semantic", lambda _t: _semantic_stub())
    monkeypatch.setattr(
        analysis, "compute_price_market_pillar",
        lambda **_k: {"verdict": "Plutôt aligné", "explanation": "", "confidence": "Faible"},
    )
    result = run_full_analysis("Maison à Metz, grand jardin.")
    assert result["actions"]["highlights"] == ["Grand jardin arboré", "Garage double"]


def test_levier_dpe_derive_fusionne_dans_negotiation(monkeypatch):
    """Le DPE G du listing produit un levier derive present dans `negotiation`,
    meme si le LLM n'a renvoye aucun levier."""
    monkeypatch.setattr(analysis, "analyze_semantic", lambda _t: _semantic_stub())
    monkeypatch.setattr(
        analysis, "compute_price_market_pillar",
        lambda **_k: {"verdict": "Plutôt aligné", "explanation": "", "confidence": "Faible"},
    )
    result = run_full_analysis("Maison à Metz, DPE G.")
    assert any("DPE G" in lev for lev in result["actions"]["negotiation"])


def test_atouts_jamais_dans_les_leviers(monkeypatch):
    """Garde anti-regression du symptome signale : les points forts du bien ne
    doivent pas se retrouver dans les leviers de negociation."""
    monkeypatch.setattr(analysis, "analyze_semantic", lambda _t: _semantic_stub())
    monkeypatch.setattr(
        analysis, "compute_price_market_pillar",
        lambda **_k: {"verdict": "Plutôt aligné", "explanation": "", "confidence": "Faible"},
    )
    result = run_full_analysis("Maison à Metz.")
    assert "Grand jardin arboré" not in result["actions"]["negotiation"]
