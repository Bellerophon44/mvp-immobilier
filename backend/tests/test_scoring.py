from app.scoring import compute_global_score


def _semantic(transparency=80, risk="faible"):
    return {"transparency_score": transparency, "risk_level": risk}


def test_aligned_price_transparent_low_risk_is_strong():
    result = compute_global_score(
        {"verdict": "Plutôt aligné", "confidence": "Élevée"},
        _semantic(),
    )
    # 40 (prix aligné) + 30 (transparence >=70) + 30 (risque faible)
    assert result["score"] == 100
    assert result["verdict"] == "Cohérence forte"
    assert result["confidence"] == "Élevée"


def test_strongly_overpriced_drags_score_down():
    result = compute_global_score(
        {"verdict": "Fortement sur-positionné", "confidence": "Moyenne"},
        _semantic(),
    )
    # 12 (prix fortement sur-positionné) + 30 (transparence) + 30 (risque faible)
    assert result["score"] == 72
    assert result["confidence"] == "Moyenne"


def test_indetermine_price_uses_neutral_floor():
    result = compute_global_score(
        {"verdict": "Indéterminé", "confidence": "Faible"},
        _semantic(transparency=30, risk="élevé"),
    )
    # 22 (prix indéterminé) + 6 (transparence faible) + 6 (risque élevé)
    assert result["score"] == 34
    assert result["verdict"] == "Cohérence faible"
    assert result["confidence"] == "Faible"


def test_score_equals_pillar_breakdown_sum():
    """Invariant clé : le score global est EXACTEMENT la somme des points des
    piliers (prix /40 + transparence /30 + risque /30 = /100), pour que
    l'affichage des barres et du score concordent."""
    for price_verdict in (
        "Plutôt aligné", "Sous-positionné", "Légèrement sur-positionné",
        "Fortement sur-positionné", "Indéterminé",
    ):
        for transparency in (90, 50, 20):
            for risk in ("faible", "modéré", "élevé", "incertain"):
                result = compute_global_score(
                    {"verdict": price_verdict, "confidence": "Moyenne"},
                    _semantic(transparency=transparency, risk=risk),
                )
                b = result["breakdown"]
                assert b["semantic"] == b["transparency"] + b["risk"]
                assert result["score"] == b["price"] + b["semantic"]
                assert 0 <= result["score"] <= 100


def test_score_is_bounded():
    result = compute_global_score(
        {"verdict": "Plutôt aligné", "confidence": "Élevée"},
        _semantic(transparency=100, risk="faible"),
    )
    assert 0 <= result["score"] <= 100
