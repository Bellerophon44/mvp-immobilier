"use client";

import { useState } from "react";
import { analyzeListing, ApiResult } from "../lib/api";
import AnalyzerInput, { AnalyzerMode } from "../components/design/AnalyzerInput";
import VerdictHeader from "../components/design/VerdictHeader";
import PillarBar from "../components/design/PillarBar";
import ChecklistCard from "../components/design/ChecklistCard";
import LeversList from "../components/design/LeversList";
import Wordmark from "../components/design/Wordmark";
import ScopeBadge from "../components/design/ScopeBadge";
import Footer from "../components/design/Footer";
import { Copy } from "../components/design/Icons";

type AppState = "idle" | "analyzing" | "result";

function priceVerdictToScore(verdict: string): number {
  const v = verdict.toLowerCase();
  if (v.includes("aligné")) return 35;
  if (v.includes("légèrement")) return 25;
  if (v.includes("fortement") || v.includes("fort")) return 10;
  if (v.includes("sous")) return 30;
  return 15;
}

function transparencyVerdictToScore(verdict: string): number {
  const v = verdict.toLowerCase();
  if (v.includes("bonne")) return 25;
  if (v.includes("moyenne")) return 15;
  return 5;
}

function riskVerdictToScore(verdict: string): number {
  const v = verdict.toLowerCase();
  if (v.includes("faible")) return 25;
  if (v.includes("modéré") || v.includes("modere")) return 15;
  return 5;
}

function verdictColor(verdict: string): string {
  const v = verdict.toLowerCase();
  if (v.includes("bonne") || v.includes("faible") || v.includes("aligné") || v.includes("sous")) return "var(--moss)";
  if (v.includes("légèrement") || v.includes("moyenne") || v.includes("modéré")) return "var(--ochre)";
  return "var(--brick)";
}

function Header() {
  return (
    <header style={{
      position: "sticky",
      top: 0,
      zIndex: 10,
      backdropFilter: "blur(8px)",
      WebkitBackdropFilter: "blur(8px)",
      background: "color-mix(in oklab, var(--parchment), transparent 20%)",
      borderBottom: "1px solid var(--stone-line)",
    }}>
      <div style={{
        maxWidth: 960,
        margin: "0 auto",
        padding: "14px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <Wordmark size={22} />
        <ScopeBadge />
      </div>
    </header>
  );
}

function AnalyzingState() {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "96px 0", gap: 28 }}>
      <div style={{ width: 132, height: 132, position: "relative" }}>
        <svg width="132" height="132" viewBox="0 0 132 132" style={{ animation: "rotate 1.6s linear infinite" }}>
          <circle cx="66" cy="66" r="54" fill="none" stroke="var(--stone-line)" strokeWidth="6" />
          <circle cx="66" cy="66" r="54" fill="none" stroke="var(--brick)" strokeWidth="6"
            strokeDasharray="339.3" strokeDashoffset="240" strokeLinecap="round" />
        </svg>
        <style>{`@keyframes rotate { to { transform: rotate(360deg); } }`}</style>
      </div>
      <div style={{ textAlign: "center" }}>
        <div className="t-eyebrow" style={{ marginBottom: 8 }}>Analyse en cours</div>
        <div style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: 24, color: "var(--ink-2)" }}>
          Lecture de l&apos;annonce, comparables locaux, calcul du score…
        </div>
      </div>
    </div>
  );
}

function SecondaryRow() {
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(3, 1fr)",
      gap: 12,
      paddingTop: 32,
      borderTop: "1px solid var(--stone-line)",
    }}>
      {[
        { n: "01", t: "Pilier prix", d: "Médiane locale et écart calculés sur ≥ 3 comparables." },
        { n: "02", t: "Pilier sémantique", d: "L'annonce est-elle claire ? Quels signaux manquent ?" },
        { n: "03", t: "Pilier global", d: "Score 0 – 100 et verdict en une phrase." },
      ].map((c) => (
        <div key={c.n}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--stone)", letterSpacing: "0.06em", marginBottom: 8 }}>
            {c.n}
          </div>
          <div style={{ fontFamily: "var(--font-serif)", fontSize: 20, color: "var(--ink)", lineHeight: 1.15, marginBottom: 6 }}>
            {c.t}
          </div>
          <div style={{ fontFamily: "var(--font-sans)", fontSize: 13, color: "var(--ink-3)", lineHeight: 1.5 }}>
            {c.d}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function HomePage() {
  const [appState, setAppState] = useState<AppState>("idle");
  const [result, setResult] = useState<ApiResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleAnalyze({ mode, value }: AnalyzerMode) {
    setAppState("analyzing");
    setError(null);
    try {
      const res = await analyzeListing(value, mode);
      setResult(res);
      setAppState("result");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur lors de l'analyse.";
      setError(msg);
      setAppState("idle");
    }
  }

  function handleReset() {
    setResult(null);
    setAppState("idle");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handleCopy() {
    if (!result) return;
    const lines = [
      `Score de cohérence : ${result.global_score} / 100`,
      `Verdict : ${result.verdict}`,
      `Confiance : ${result.confidence}`,
      "",
      ...result.pillars.map((p) => `${p.label} : ${p.verdict}\n${p.explanation}`),
      "",
      "À vérifier avant la visite :",
      ...result.actions.check.map((c) => `- ${c}`),
      "",
      "Questions à poser au vendeur :",
      ...result.actions.questions.map((q) => `- ${q}`),
      "",
      "Leviers de négociation :",
      ...result.actions.negotiation.map((n) => `- ${n}`),
    ];
    navigator.clipboard.writeText(lines.join("\n")).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  const pricePillar        = result?.pillars[0];
  const transparencyPillar = result?.pillars[1];
  const riskPillar         = result?.pillars[2];

  const priceScore = pricePillar ? priceVerdictToScore(pricePillar.verdict) : 0;
  const semanticRaw =
    (transparencyPillar ? transparencyVerdictToScore(transparencyPillar.verdict) : 0) +
    (riskPillar ? riskVerdictToScore(riskPillar.verdict) : 0);
  const semanticScore = Math.round(semanticRaw * 60 / 50);

  const verdictSummary = transparencyPillar?.explanation || pricePillar?.explanation || "";

  return (
    <div style={{ minHeight: "100vh", background: "var(--parchment)", color: "var(--ink)" }}>
      <Header />

      <main style={{
        maxWidth: 720,
        margin: "0 auto",
        padding: appState === "idle" ? "96px 24px 64px" : "48px 24px 64px",
        transition: "padding var(--dur-page) var(--ease-paper)",
      }}>

        {/* ── IDLE ── */}
        {appState === "idle" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 40 }}>
            <div>
              <div className="t-eyebrow" style={{ marginBottom: 16 }}>
                Analyseur de cohérence d&apos;annonces
              </div>
              <h1 style={{
                fontFamily: "var(--font-serif)",
                fontSize: 56,
                lineHeight: 1.02,
                letterSpacing: "-0.02em",
                color: "var(--ink)",
                margin: "0 0 18px",
                fontWeight: 400,
                maxWidth: 620,
              }}>
                Ce prix et cette annonce<br />
                sont-ils{" "}
                <em style={{ color: "var(--brick)", fontStyle: "italic" }}>cohérents</em>{" "}
                avec<br />
                le marché local&nbsp;?
              </h1>
              <p style={{
                fontFamily: "var(--font-sans)",
                fontSize: 17,
                lineHeight: 1.55,
                color: "var(--ink-2)",
                margin: 0,
                maxWidth: 540,
              }}>
                Collez l&apos;URL ou le texte d&apos;une annonce. Nous renvoyons un score
                de cohérence, trois piliers de lecture, et une liste de points à vérifier
                avant la visite.
              </p>
            </div>

            <AnalyzerInput onAnalyze={handleAnalyze} />

            {error && (
              <div style={{
                padding: "14px 16px",
                background: "var(--brick-soft)",
                border: "1px solid var(--brick)",
                borderRadius: 4,
                fontFamily: "var(--font-sans)",
                fontSize: 14,
                color: "var(--brick-deep)",
                lineHeight: 1.5,
              }}>
                {error}
              </div>
            )}

            <SecondaryRow />
          </div>
        )}

        {/* ── ANALYZING ── */}
        {appState === "analyzing" && <AnalyzingState />}

        {/* ── RESULT ── */}
        {appState === "result" && result && (
          <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            {/* Action bar */}
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              paddingBottom: 16,
              borderBottom: "1px solid var(--stone-line)",
            }}>
              <button onClick={handleReset} style={{
                background: "transparent",
                border: "none",
                padding: 0,
                cursor: "pointer",
                fontFamily: "var(--font-sans)",
                fontSize: 13,
                color: "var(--ink-3)",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}>
                ← Analyser une autre annonce
              </button>
              <button onClick={handleCopy} style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "9px 14px",
                background: "var(--paper)",
                border: "1px solid var(--stone-line)",
                borderRadius: 4,
                color: "var(--ink)",
                fontFamily: "var(--font-sans)",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
              }}>
                <Copy size={14} />
                {copied ? "Rapport copié" : "Copier le rapport"}
              </button>
            </div>

            {/* Score + verdict */}
            <VerdictHeader
              score={result.global_score}
              summary={verdictSummary}
              confidence={result.confidence}
            />

            {/* Pillar bars */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <PillarBar
                name="Pilier prix"
                score={priceScore}
                max={40}
                color={verdictColor(pricePillar?.verdict || "")}
                legend={pricePillar?.verdict || ""}
              />
              <PillarBar
                name="Pilier sémantique"
                score={semanticScore}
                max={60}
                color={verdictColor(riskPillar?.verdict || "")}
                legend={riskPillar ? `Risques : ${riskPillar.verdict.toLowerCase()}` : ""}
              />
            </div>

            {/* Price pillar detail card */}
            {pricePillar && (
              <div style={{
                background: "var(--paper)",
                border: "1px solid var(--stone-line)",
                borderRadius: 4,
                padding: "16px 20px",
              }}>
                <div className="t-eyebrow" style={{ marginBottom: 8 }}>{pricePillar.label}</div>
                <div style={{
                  fontFamily: "var(--font-sans)",
                  fontSize: 14,
                  color: "var(--ink-2)",
                  lineHeight: 1.55,
                }}>
                  {pricePillar.explanation}
                </div>
              </div>
            )}

            {/* À vérifier */}
            <ChecklistCard
              eyebrow="À vérifier avant la visite"
              items={result.actions.check.map((c) => ({ title: c }))}
            />

            {/* Questions */}
            <ChecklistCard
              eyebrow="Questions à poser au vendeur"
              items={result.actions.questions.map((q) => ({ title: q }))}
            />

            {/* Leviers */}
            <LeversList
              items={result.actions.negotiation.map((n) => ({ quote: n }))}
            />
          </div>
        )}

        <Footer />
      </main>
    </div>
  );
}
