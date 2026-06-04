from app.scoring import compute_global_score


def _semantic(transparency=80, risk="faible"):
    return {"transparency_score": transparency, "risk_level": risk}


def test_aligned_price_transparent_low_risk_is_strong():
    result = compute_global_score(
        {"verdict": "Plutôt aligné", "confidence": "Élevée"},
        _semantic(),
    )
    assert result["score"] == 90
    assert result["verdict"] == "Cohérence forte"
    assert result["confidence"] == "Élevée"


def test_strongly_overpriced_drags_score_down():
    result = compute_global_score(
        {"verdict": "Fortement sur-positionné", "confidence": "Moyenne"},
        _semantic(),
    )
    assert result["score"] == 62
    assert result["confidence"] == "Moyenne"


def test_indetermine_price_uses_neutral_floor():
    result = compute_global_score(
        {"verdict": "Indéterminé", "confidence": "Faible"},
        _semantic(transparency=30, risk="élevé"),
    )
    # 22 (prix indéterminé) + 5 (transparence faible) + 5 (risque élevé)
    assert result["score"] == 32
    assert result["verdict"] == "Cohérence faible"
    assert result["confidence"] == "Faible"


def test_score_is_bounded():
    result = compute_global_score(
        {"verdict": "Plutôt aligné", "confidence": "Élevée"},
        _semantic(transparency=100, risk="faible"),
    )
    assert 0 <= result["score"] <= 100
