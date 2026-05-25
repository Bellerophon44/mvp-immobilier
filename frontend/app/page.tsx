"use client";

import { useState } from "react";
import { analyzeListing } from "../lib/api";
import ScoreResult from "../components/ScoreResult";
import Pillars from "../components/Pillars";
import Actions from "../components/Actions";

export default function HomePage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    setLoading(true);
    setError(null);
    try {
      const res = await analyzeListing(text);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Une erreur est survenue. Réessayez dans un instant.");
    }
    setLoading(false);
  }

  function handleReset() {
    setResult(null);
    setText("");
    setError(null);
  }

  return (
    <main className="app-container">
      {!result && (
        <>
          <section className="hero">
            <span className="hero-eyebrow">Lecture critique d'annonce</span>
            <h1 className="hero-title">
              Avant d'acheter, faites lire l'annonce par un œil neuf.
            </h1>
            <p className="hero-subtitle">
              Une analyse en clair de ce que l'annonce dit, de ce qu'elle ne dit
              pas, et des bonnes questions à poser au vendeur.
            </p>
            <ul className="hero-points">
              <li>Pas d'estimation de prix</li>
              <li>Données observables uniquement</li>
              <li>Résultat en ~10 secondes</li>
            </ul>
          </section>

          <section className="input-card">
            <label htmlFor="listing-input" className="input-label">
              Texte de l'annonce
              <span className="input-hint">
                — ou collez l'URL d'une annonce
              </span>
            </label>

            <textarea
              id="listing-input"
              className="input-textarea"
              placeholder={
                "Exemple : Appartement T3 lumineux à Metz Sablon, 75 m², 195 000 €, refait à neuf, proche tram, DPE D, charges 80 €/mois...\n\nOu collez directement le lien de l'annonce."
              }
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
            />

            <div className="input-row">
              <span className="input-counter">
                {text.length > 0 ? `${text.length} caractères` : ""}
              </span>
              <button
                className="btn-primary"
                onClick={handleAnalyze}
                disabled={loading || !text.trim()}
              >
                {loading && <span className="loader" aria-hidden />}
                {loading ? "Analyse en cours…" : "Analyser cette annonce"}
              </button>
            </div>

            {error && <div className="error-banner">{error}</div>}
          </section>

          <p className="legal-note">
            Cette analyse est un outil d'aide à la décision. Elle ne remplace pas
            l'avis d'un professionnel et ne constitue pas une estimation de prix.
          </p>
        </>
      )}

      {result && (
        <section className="result-stack">
          <ScoreResult result={result} />
          <div>
            <h2 className="section-title">Trois axes de lecture</h2>
            <Pillars pillars={result.pillars} />
          </div>
          <Actions actions={result.actions} />
          <div className="reset-row">
            <button className="btn-secondary" onClick={handleReset}>
              Analyser une autre annonce
            </button>
          </div>
        </section>
      )}
    </main>
  );
}
