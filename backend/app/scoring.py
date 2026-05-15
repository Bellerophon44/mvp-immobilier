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
    else:
        score += 15
        explanations.append("Positionnement prix incertain.")

    # =========================
    # 2. Transparence (30 pts)
    # =========================

    transparency = semantic_pillar.get("transparency_score", 50)

    if transparency >= 70:
        score += 25
        explanations.append("Annonce claire et transparente.")
    elif transparency >= 40:
        score += 15
        explanations.append("Annonce partiellement transparente.")
    else:
        score += 5
        explanations.append("Annonce peu transparente.")

    # =========================
    # 3. Risques (30 pts)
    # =========================

    risk = (semantic_pillar.get("risk_level") or "").lower()

    if "faible" in risk:
        score += 25
        explanations.append("Peu de risques identifiés.")
    elif "modéré" in risk:
        score += 15
        explanations.append("Quelques incertitudes à vérifier.")
    elif "élevé" in risk:
        score += 5
        explanations.append("Risques importants identifiés.")
    else:
        score += 10
        explanations.append("Niveau de risque incertain.")

    # =========================
    # Bornage du score
    # =========================

    score = max(0, min(100, score))

    # =========================
    # Verdict global
    # =========================

    if score >= 80:
        verdict = "Cohérence forte"
    elif score >= 60:
        verdict = "À creuser"
    elif score >= 40:
        verdict = "Risque élevé"
    else:
        verdict = "Cohérence faible"

    # =========================
    # Confiance globale
    # =========================

    price_confidence = (price_pillar.get("confidence") or "").lower()

    if price_confidence == "élevée":
        confidence = "Élevée"
    elif price_confidence == "moyenne":
        confidence = "Moyenne"
    else:
        confidence = "Faible"

    return {
        "score": score,
        "verdict": verdict,
        "confidence": confidence,
        "explanations": explanations
    }
