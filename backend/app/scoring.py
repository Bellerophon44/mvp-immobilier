def compute_global_score(price_pillar: dict, semantic_pillar: dict) -> dict:
    """
    Calcule le score global du bien à partir des piliers analytiques.

    Pondération **40 / 30 / 30** (prix / transparence / risque) = 100 points, de
    sorte que le score global est EXACTEMENT la somme des points des piliers
    (prix + sémantique). La ventilation est renvoyée dans `breakdown` pour que le
    front affiche les mêmes nombres que le score (pas de recalcul divergent).

    Entrées attendues :
    - price_pillar : dict avec les clés `verdict` (str), `confidence` (str).
    - semantic_pillar : dict avec `transparency_score` (0-100), `risk_level` (str).
    """

    explanations = []

    # --------------------------
    # 1. PILIER PRIX / MARCHÉ (40 points max)
    # --------------------------
    # On matche sur les libellés réels produits par market_stats :
    # "Plutôt aligné", "Légèrement sur‑positionné", "Fortement sur‑positionné",
    # "Sous‑positionné", "Indéterminé".
    price_verdict = price_pillar.get("verdict", "").lower()

    if "aligné" in price_verdict:
        price_points = 40
        explanations.append("Prix cohérent avec la fourchette observée localement.")
    elif "sous" in price_verdict:
        price_points = 32
        explanations.append("Prix sous la fourchette observée localement.")
    elif "légèrement" in price_verdict:
        price_points = 28
        explanations.append("Prix un peu au‑dessus de la fourchette, mais dans les niveaux constatés.")
    elif "fortement" in price_verdict:
        price_points = 12
        explanations.append("Prix nettement au‑dessus du marché observable.")
    else:
        price_points = 22
        explanations.append("Positionnement prix indéterminé (comparables insuffisants).")

    # =========================
    # 2. Transparence (30 pts max)
    # =========================
    transparency = semantic_pillar.get("transparency_score", 50)

    if transparency >= 70:
        transparency_points = 30
        explanations.append("Annonce claire et transparente.")
    elif transparency >= 40:
        transparency_points = 18
        explanations.append("Annonce partiellement transparente.")
    else:
        transparency_points = 6
        explanations.append("Annonce peu transparente.")

    # =========================
    # 3. Risques (30 pts max)
    # =========================
    risk = (semantic_pillar.get("risk_level") or "").lower()

    if "faible" in risk:
        risk_points = 30
        explanations.append("Peu de risques identifiés.")
    elif "modéré" in risk:
        risk_points = 18
        explanations.append("Quelques incertitudes à vérifier.")
    elif "élevé" in risk:
        risk_points = 6
        explanations.append("Risques importants identifiés.")
    else:
        risk_points = 12
        explanations.append("Niveau de risque incertain.")

    # =========================
    # Agrégation (somme exacte des piliers, bornée par sécurité)
    # =========================
    semantic_points = transparency_points + risk_points
    score = max(0, min(100, price_points + semantic_points))

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
        "explanations": explanations,
        # Ventilation par pilier (pour un affichage cohérent côté front) :
        # prix(/40) + transparence(/30) + risque(/30) = score(/100).
        "breakdown": {
            "price": price_points,
            "transparency": transparency_points,
            "risk": risk_points,
            "semantic": semantic_points,
        },
    }

