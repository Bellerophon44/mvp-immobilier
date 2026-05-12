from app.llm_semantic import analyze_semantic
from app.market_stats import compute_price_market_pillar
from app.scoring import compute_global_score


def run_full_analysis(raw_text: str) -> dict:
    """
    Fonction centrale du MVP.
    Orchestration complète de l'analyse.
    """

    # 1. Analyse sémantique (IA)
    semantic_result = analyze_semantic(raw_text)

    # 2. Analyse prix / marché local observable
    price_market_pillar = compute_price_market_pillar(raw_text)

    # 3. Construction des piliers
    pillars = [
        {
            "label": "Prix vs marché local",
            "verdict": price_market_pillar["verdict"],
            "explanation": price_market_pillar["explanation"]
        },
        {
            "label": "Transparence de l’annonce",
            "verdict": semantic_result["verdict"],
            "explanation": semantic_result["summary"]
        },
        {
            "label": "Risques et incertitudes",
            "verdict": semantic_result["risk_level"],
            "explanation": semantic_result["risk_summary"]
        }
    ]

    # 4. Score global
    score_block = compute_global_score(
        price_pillar=price_market_pillar,
        semantic_pillar=semantic_result
    )

    # 5. Actions concrètes
    actions = {
        "check": semantic_result["to_check"],
        "questions": semantic_result["questions"],
        "negotiation": semantic_result["negotiation_levers"]
    }

    # 6. Réponse finale
    return {
        "global_score": score_block["score"],
        "verdict": score_block["verdict"],
        "confidence": score_block["confidence"],
        "pillars": pillars,
        "actions": actions
    }
