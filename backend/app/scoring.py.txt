def compute_global_score(price_pillar: dict, semantic_pillar: dict) -> dict:
    """
    Calcule le score global du bien à partir des piliers analytiques.

    Entrées attendues :
    - price_pillar : dict avec les clés
        - verdict        (str)
        - confidence     (str)

    - semantic_pillar : dict avec les clés
        - transparency_score   (int ou float sur 100)
        - risk_level           (str)

    Sortie :
    - score global (0 à 100)
    - verdict humain
    - niveau de confiance global
    """

    score = 0
    explanations = []

    # --------------------------
    # 1. PILIER PRIX / MARCHÉ (40 points max)
    # --------------------------

    price_verdict = price_pillar.get("verdict", "").lower()

    if "aligné" in price_verdict:
        score += 35
        explanations.append("Prix globalement cohérent avec le marché local.")
    elif "modéré" in price_verdict:
        score += 25
        explanations.append("Prix légèrement au‑dessus du marché observable.")
    elif "fort" in price_verdict:
        score += 10
        explanations.append("Prix nettement au‑dessus du marché observable.")
    elif "sous" in price_verdict:
        score += 30
        explanations.append("Prix inférieur aux tendances observées localement.")
