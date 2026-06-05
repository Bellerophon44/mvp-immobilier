"use client";

import { useState } from "react";
import { analyzeListing, sendFeedback, ApiResult, LocalContext } from "../lib/api";
import AnalyzerInput, { AnalyzerMode } from "../components/design/AnalyzerInput";
import VerdictHeader from "../components/design/VerdictHeader";
import PillarBar from "../components/design/PillarBar";
import ChecklistCard from "../components/design/ChecklistCard";
import LeversList from "../components/design/LeversList";
import Wordmark from "../components/design/Wordmark";
import ScopeBadge from "../components/design/ScopeBadge";
import Footer from "../components/design/Footer";
import FeedbackForm from "../components/design/FeedbackForm";
import { Copy, Download, MapPin, Seal } from "../components/design/Icons";
import { METZ_DISTRICTS } from "../lib/districts";

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

function scopeLabel(p: ApiResult["pillars"][number]): string | null {
  if (!p.scope || !p.scope_name) return null;
  const base =
    p.scope === "quartier" ? `Quartier ${p.scope_name}`
    : p.scope === "secteur" ? `Secteur ${p.scope_name}`
    : p.scope_name;
  const band = p.dpe_band ? ` · DPE ${p.dpe_band}` : "";
  const n = p.n_comparables ? ` · ${p.n_comparables} comparables` : "";
  return `${base}${band}${n}`;
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
        { n: "01", t: "Pilier prix", d: "Médiane du quartier et écart calculés sur ≥ 3 comparables messins." },
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

// Statut de cohérence d'une allégation locale (couche B) -> couleur / libellé.
const CLAIM_STATUS: Record<string, { color: string; label: string }> = {
  coherent: { color: "var(--moss)", label: "Cohérent" },
  a_verifier: { color: "var(--ochre)", label: "À vérifier" },
  peu_plausible: { color: "var(--brick)", label: "Peu plausible" },
};

function claimMeta(status: string) {
  return CLAIM_STATUS[status] || CLAIM_STATUS.a_verifier;
}

// Bloc "Contexte local" : profil curaté du quartier (couche A) + contrôle de
// cohérence des allégations de l'annonce (couche B). Volontairement non-scoré
// (comme la carte prix). Distances approximatives au niveau du quartier — pas un
// 4e pilier, on garde le score 40/30/30 et "pas de fausse précision".
function LocalContextCard({ context }: { context: LocalContext }) {
  const claims = context.claims || [];
  return (
    <div style={{
      background: "var(--paper)",
      border: "1px solid var(--stone-line)",
      borderRadius: 4,
      padding: "16px 20px",
    }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 8,
        marginBottom: 8,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <MapPin size={14} style={{ color: "var(--stone)" }} />
          <div className="t-eyebrow">Contexte local — {context.district}</div>
        </div>
        {/* Cachet « édition Metz » : losange net à 20 px. L'alérion (AlerionSeal)
            est réservé aux grands formats (≥ 64 px) où il reste lisible. */}
        <Seal size={20} style={{ color: "var(--jaumont)" }} />
      </div>
      {context.address && (
        <div style={{
          fontFamily: "var(--font-sans)",
          fontSize: 13,
          color: "var(--ink-3)",
          marginBottom: 8,
        }}>
          Adresse indiquée : {context.address}
        </div>
      )}
      <div style={{
        fontFamily: "var(--font-serif)",
        fontStyle: "italic",
        fontSize: 18,
        color: "var(--ink-2)",
        lineHeight: 1.35,
        marginBottom: 14,
      }}>
        {context.summary}
      </div>
      <dl style={{ margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
        {context.facts.map((f) => (
          <div key={f.label} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <dt style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              letterSpacing: "0.04em",
              color: "var(--stone)",
              textTransform: "uppercase",
            }}>
              {f.label}
            </dt>
            <dd style={{
              margin: 0,
              fontFamily: "var(--font-sans)",
              fontSize: 14,
              color: "var(--ink-2)",
              lineHeight: 1.5,
            }}>
              {f.value}
            </dd>
          </div>
        ))}
      </dl>

      {/* Couche B : cohérence des allégations de l'annonce vs profil quartier */}
      {claims.length > 0 && (
        <div style={{
          marginTop: 16,
          paddingTop: 14,
          borderTop: "1px solid var(--stone-line)",
        }}>
          <div className="t-eyebrow" style={{ marginBottom: 10 }}>
            Allégations de l&apos;annonce
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {claims.map((c, i) => {
              const meta = claimMeta(c.status);
              return (
                <div key={`${c.text}-${i}`} style={{ display: "flex", gap: 10 }}>
                  <span style={{
                    flexShrink: 0,
                    marginTop: 2,
                    width: 9,
                    height: 9,
                    borderRadius: 999,
                    background: meta.color,
                  }} />
                  <div>
                    <div style={{
                      fontFamily: "var(--font-sans)",
                      fontSize: 14,
                      color: "var(--ink)",
                      lineHeight: 1.4,
                    }}>
                      <span style={{ fontStyle: "italic" }}>« {c.text} »</span>
                      {"  "}
                      <span style={{ color: meta.color, fontWeight: 500, fontSize: 12 }}>
                        · {meta.label}
                      </span>
                    </div>
                    <div style={{
                      fontFamily: "var(--font-sans)",
                      fontSize: 13,
                      color: "var(--ink-3)",
                      lineHeight: 1.5,
                      marginTop: 2,
                    }}>
                      {c.note}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div style={{
        marginTop: 14,
        paddingTop: 12,
        borderTop: "1px solid var(--stone-line)",
        fontFamily: "var(--font-sans)",
        fontSize: 12,
        color: "var(--ink-3)",
        lineHeight: 1.5,
      }}>
        {context.precision === "adresse"
          ? "Distances à vol d'oiseau depuis l'adresse — non comptées dans le score (temps de trajet réel à venir)."
          : "Repères indicatifs au niveau du quartier — non comptés dans le score."}
      </div>
    </div>
  );
}

export default function HomePage() {
  const [appState, setAppState] = useState<AppState>("idle");
  const [result, setResult] = useState<ApiResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  // Dernière entrée analysée, conservée pour ré-analyser avec un quartier choisi.
  const [lastInput, setLastInput] = useState<AnalyzerMode | null>(null);
  const [refining, setRefining] = useState(false);
  const [selectedDistrict, setSelectedDistrict] = useState("");
  // Identifiant opaque genere cote client, joint au feedback pour relier un
  // retour a une analyse sans modifier le contrat /analyze.
  const [analysisId, setAnalysisId] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);
  // Adresse saisie par l'utilisateur pour affiner le feedback local (alternative
  // manuelle au géocodage de la couche C).
  const [addressInput, setAddressInput] = useState("");

  async function handleAnalyze({ mode, value }: AnalyzerMode) {
    setAppState("analyzing");
    setError(null);
    setSelectedDistrict("");
    setAddressInput("");
    setLastInput({ mode, value });
    setFeedbackSent(false);
    try {
      const res = await analyzeListing(value, mode);
      setResult(res);
      setAnalysisId(crypto.randomUUID());
      setAppState("result");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur lors de l'analyse.";
      setError(msg);
      setAppState("idle");
    }
  }

  // Ré-analyse affinée : par quartier (#6-A, pilier prix) et/ou par adresse
  // saisie (feedback local, alternative manuelle au géocodage).
  async function handleRefine(district: string, address: string) {
    if (!lastInput || (!district && !address.trim())) return;
    setRefining(true);
    setError(null);
    setFeedbackSent(false);
    try {
      const res = await analyzeListing(lastInput.value, lastInput.mode, district, address);
      setResult(res);
      setAnalysisId(crypto.randomUUID());
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur lors de l'analyse.";
      setError(msg);
    } finally {
      setRefining(false);
    }
  }

  function handleDistrictChange(district: string) {
    setSelectedDistrict(district);
    handleRefine(district, addressInput);
  }

  function handleAddressSubmit() {
    if (!addressInput.trim()) return;
    handleRefine(selectedDistrict, addressInput);
  }

  function handleReset() {
    setResult(null);
    setError(null);
    setSelectedDistrict("");
    setFeedbackSent(false);
    setAddressInput("");
    setAppState("idle");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleFeedback(rating: number, comment: string) {
    if (!result) return;
    setFeedbackSent(true);
    await sendFeedback({
      rating,
      comment: comment || undefined,
      analysis_id: analysisId || undefined,
      global_score: result.global_score,
      verdict: result.verdict,
    });
  }

  function buildReportText(): string {
    if (!result) return "";
    const lc = result.local_context;
    const lines = [
      `Score de cohérence : ${result.global_score} / 100`,
      `Verdict : ${result.verdict}`,
      `Confiance : ${result.confidence}`,
      "",
      ...result.pillars.map((p) => `${p.label} : ${p.verdict}\n${p.explanation}`),
      ...(lc
        ? [
            "",
            `Contexte local — ${lc.district} :`,
            ...(lc.address ? [`Adresse indiquée : ${lc.address}`] : []),
            lc.summary,
            ...lc.facts.map((f) => `- ${f.label} : ${f.value}`),
            ...(lc.claims && lc.claims.length
              ? [
                  "",
                  "Allégations de l'annonce :",
                  ...lc.claims.map(
                    (c) => `- « ${c.text} » [${claimMeta(c.status).label}] — ${c.note}`,
                  ),
                ]
              : []),
          ]
        : []),
      "",
      "Questions à poser (vendeur / agent) :",
      ...result.actions.questions.map((q) => `- ${q}`),
      "",
      "Leviers de négociation :",
      ...result.actions.negotiation.map((n) => `- ${n}`),
    ];
    return lines.join("\n");
  }

  function handleCopy() {
    if (!result) return;
    navigator.clipboard.writeText(buildReportText()).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  function handleDownload() {
    if (!result) return;
    const blob = new Blob([buildReportText()], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const stamp = new Date().toISOString().slice(0, 10);
    const a = document.createElement("a");
    a.href = url;
    a.download = `analyse-cohérence-${stamp}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  const pricePillar        = result?.pillars[0];
  const transparencyPillar = result?.pillars[1];
  const riskPillar         = result?.pillars[2];

  // Barres = points exacts renvoyés par le backend, pour que
  // prix + sémantique = score global. Repli sur l'heuristique de verdict
  // seulement si l'API ne fournit pas encore `points` (anciennes réponses).
  const priceScore = pricePillar?.points
    ?? (pricePillar ? priceVerdictToScore(pricePillar.verdict) : 0);
  const semanticScore =
    (transparencyPillar?.points
      ?? (transparencyPillar ? Math.round(transparencyVerdictToScore(transparencyPillar.verdict) * 30 / 25) : 0)) +
    (riskPillar?.points
      ?? (riskPillar ? Math.round(riskVerdictToScore(riskPillar.verdict) * 30 / 25) : 0));

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
                Analyse d&apos;annonces immobilières · Metz &amp; Moselle
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
                le marché messin, quartier par quartier&nbsp;?
              </h1>
              <p style={{
                fontFamily: "var(--font-sans)",
                fontSize: 17,
                lineHeight: 1.55,
                color: "var(--ink-2)",
                margin: 0,
                maxWidth: 540,
              }}>
                Le livre foncier n&apos;est pas public : impossible de savoir à quel
                prix s&apos;est vraiment vendu le voisin. Nous reconstituons le marché
                local à partir des annonces réelles — du Sablon à Queuleu, de
                Devant-les-Ponts à l&apos;Outre-Seille — et comparons votre annonce,
                comparable par comparable. Score de cohérence, trois piliers de lecture,
                et les points à vérifier avant la visite.
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
              <button onClick={handleDownload} aria-label="Télécharger le rapport en .md" style={{
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
                <Download size={14} />
                Télécharger (.md)
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
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  marginBottom: 8,
                  flexWrap: "wrap",
                }}>
                  <div className="t-eyebrow">{pricePillar.label}</div>
                  {scopeLabel(pricePillar) && (
                    <span style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "4px 9px",
                      border: "1px solid var(--stone-line)",
                      borderRadius: 999,
                      background: "var(--parchment)",
                      color: "var(--ink-3)",
                      fontFamily: "var(--font-sans)",
                      fontSize: 11,
                      lineHeight: 1,
                      fontWeight: 500,
                    }}>
                      <MapPin size={12} style={{ color: "var(--stone)" }} />
                      {scopeLabel(pricePillar)}
                    </span>
                  )}
                </div>
                <div style={{
                  fontFamily: "var(--font-sans)",
                  fontSize: 14,
                  color: "var(--ink-2)",
                  lineHeight: 1.55,
                }}>
                  {pricePillar.explanation}
                </div>

                {/* Affinage par quartier quand l'analyse est restée au niveau ville */}
                {pricePillar.refinable && (
                  <div style={{
                    marginTop: 14,
                    paddingTop: 14,
                    borderTop: "1px solid var(--stone-line)",
                  }}>
                    <label style={{
                      display: "block",
                      fontFamily: "var(--font-sans)",
                      fontSize: 13,
                      color: "var(--ink-2)",
                      lineHeight: 1.5,
                      marginBottom: 8,
                    }}>
                      Pour une analyse plus précise, dans quel quartier se situe ce bien ?
                    </label>
                    <select
                      value={selectedDistrict}
                      disabled={refining}
                      onChange={(e) => handleDistrictChange(e.target.value)}
                      style={{
                        width: "100%",
                        maxWidth: 320,
                        padding: "9px 12px",
                        background: "var(--parchment)",
                        border: "1px solid var(--stone-line)",
                        borderRadius: 4,
                        fontFamily: "var(--font-sans)",
                        fontSize: 14,
                        color: "var(--ink)",
                        cursor: refining ? "wait" : "pointer",
                      }}
                    >
                      <option value="" disabled>Choisir un quartier…</option>
                      {METZ_DISTRICTS.map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>

                    {/* Retour visuel : la ré-analyse peut être lente (réveil du backend) */}
                    {refining && (
                      <div style={{
                        marginTop: 10,
                        fontFamily: "var(--font-sans)",
                        fontSize: 13,
                        fontStyle: "italic",
                        color: "var(--ink-3)",
                      }}>
                        Analyse du quartier {selectedDistrict} en cours…
                      </div>
                    )}
                    {!refining && error && (
                      <div style={{
                        marginTop: 10,
                        fontFamily: "var(--font-sans)",
                        fontSize: 13,
                        color: "var(--brick-deep)",
                      }}>
                        {error}
                      </div>
                    )}
                    {!refining && !error && selectedDistrict && (
                      <div style={{
                        marginTop: 10,
                        fontFamily: "var(--font-sans)",
                        fontSize: 13,
                        color: "var(--ink-3)",
                      }}>
                        Trop peu de comparables dans {selectedDistrict} pour affiner —
                        analyse maintenue à l&apos;échelle de la ville.
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Ancrage local (non-scoré) : profil quartier (A) + cohérence des
                allégations (B), et précision par adresse (alternative à la C). */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {result.local_context && (
                <LocalContextCard context={result.local_context} />
              )}

              <div style={{
                background: "var(--paper)",
                border: "1px solid var(--stone-line)",
                borderRadius: 4,
                padding: "16px 20px",
              }}>
                <label
                  htmlFor="address-refine"
                  style={{
                    display: "block",
                    fontFamily: "var(--font-sans)",
                    fontSize: 13,
                    color: "var(--ink-2)",
                    lineHeight: 1.5,
                    marginBottom: 8,
                  }}
                >
                  {result.local_context
                    ? "Adresse exacte (optionnel) — pour préciser le feedback local"
                    : "Quartier non détecté. Renseignez l'adresse pour obtenir le contexte local."}
                </label>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <input
                    id="address-refine"
                    type="text"
                    value={addressInput}
                    disabled={refining}
                    placeholder="ex. 4 rue Serpenoise, Metz"
                    onChange={(e) => setAddressInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleAddressSubmit();
                    }}
                    style={{
                      flex: "1 1 240px",
                      padding: "9px 12px",
                      background: "var(--parchment)",
                      border: "1px solid var(--stone-line)",
                      borderRadius: 4,
                      fontFamily: "var(--font-sans)",
                      fontSize: 14,
                      color: "var(--ink)",
                    }}
                  />
                  <button
                    onClick={handleAddressSubmit}
                    disabled={refining || !addressInput.trim()}
                    style={{
                      padding: "9px 16px",
                      background: "var(--ink)",
                      border: "1px solid var(--ink)",
                      borderRadius: 4,
                      color: "var(--paper)",
                      fontFamily: "var(--font-sans)",
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: refining || !addressInput.trim() ? "default" : "pointer",
                      opacity: refining || !addressInput.trim() ? 0.5 : 1,
                    }}
                  >
                    Préciser
                  </button>
                </div>
                {refining && (
                  <div style={{
                    marginTop: 10,
                    fontFamily: "var(--font-sans)",
                    fontSize: 13,
                    fontStyle: "italic",
                    color: "var(--ink-3)",
                  }}>
                    Mise à jour du feedback local en cours…
                  </div>
                )}
                <div style={{
                  marginTop: 10,
                  fontFamily: "var(--font-sans)",
                  fontSize: 12,
                  color: "var(--ink-3)",
                  lineHeight: 1.5,
                }}>
                  L&apos;adresse est géocodée pour mesurer les distances exactes au
                  bien ; à défaut, repli sur le profil du quartier.
                </div>
              </div>
            </div>

            {/* Questions (fusion à-vérifier + questions) */}
            <ChecklistCard
              eyebrow="Questions à poser (vendeur / agent)"
              items={result.actions.questions.map((q) => ({ title: q }))}
            />

            {/* Leviers */}
            <LeversList
              items={result.actions.negotiation.map((n) => ({ quote: n }))}
            />

            {/* Feedback utilisateur (9.7) */}
            <FeedbackForm sent={feedbackSent} onSubmit={handleFeedback} />
          </div>
        )}

        <Footer />
      </main>
    </div>
  );
}
