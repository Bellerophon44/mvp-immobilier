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
import { Copy, Printer, MapPin, Seal, LorraineSeal } from "../components/design/Icons";
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
    <header className="no-print" style={{
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

// Chemin de la photo héro. null tant qu'on n'a pas branché l'image libre de
// droits choisie (cf. docs/brand/LOCAL-ANCHORING.md, brief photo). La poser
// dans frontend/public/ puis renseigner ici (ex. "/hero-metz.jpg") suffit :
// le traitement N&B/grain/scrim est appliqué en CSS, une couleur fait l'affaire.
const HERO_IMAGE: string | null = null;
const HERO_ALT = "Façade en pierre de Metz";
// Crédit photo affiché en bas du hero. OBLIGATOIRE si l'image est sous licence
// à attribution (CC-BY / CC-BY-SA). Ex. "Photo : Markus Bernet · CC BY-SA 4.0 · Wikimedia Commons".
const HERO_CREDIT: string | null = null;

// Grain argentique discret (SVG feTurbulence en data-URI), posé en multiply.
const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")";

// Hero plein cadre de la home (édition Metz). Photo architecturale traitée en
// N&B chaud + grain, scrim parchemin vers le bas, titre en ink par-dessus —
// registre éditorial sanctionné par la charte (une seule photo héro). Tant
// qu'aucune image n'est branchée, un placeholder en pierre + cachet en filigrane
// tient le cadre proprement.
function HeroBanner() {
  return (
    <section aria-label="Cohérence — analyse d'annonces à Metz" style={{
      position: "relative",
      width: "100%",
      minHeight: "clamp(380px, 56vh, 560px)",
      overflow: "hidden",
      background: "var(--stone-fill)",
      borderBottom: "1px solid var(--stone-line)",
    }}>
      {HERO_IMAGE ? (
        <img src={HERO_IMAGE} alt={HERO_ALT} style={{
          position: "absolute", inset: 0, width: "100%", height: "100%",
          objectFit: "cover",
          filter: "grayscale(1) sepia(0.35) contrast(1.05) brightness(0.96)",
        }} />
      ) : (
        <div aria-hidden style={{
          position: "absolute", inset: 0,
          background: "radial-gradient(130% 120% at 72% 8%, var(--stone-fill) 0%, var(--paper) 52%, var(--parchment) 100%)",
        }}>
          <LorraineSeal size={240} style={{
            color: "var(--jaumont)", opacity: 0.13,
            position: "absolute", right: "5%", top: "12%",
          }} />
        </div>
      )}

      {/* Grain argentique */}
      <div aria-hidden style={{
        position: "absolute", inset: 0,
        backgroundImage: GRAIN, backgroundSize: "140px 140px",
        mixBlendMode: "multiply", opacity: 0.12, pointerEvents: "none",
      }} />

      {/* Scrim parchemin vers le bas, pour la lisibilité du titre en ink */}
      <div aria-hidden style={{
        position: "absolute", inset: 0,
        background: "linear-gradient(to bottom, rgba(245,241,234,0.08) 0%, rgba(245,241,234,0) 26%, rgba(245,241,234,0.74) 76%, var(--parchment) 100%)",
      }} />

      {/* Contenu */}
      <div style={{
        position: "relative",
        maxWidth: 960, margin: "0 auto",
        padding: "56px 24px 36px",
        minHeight: "clamp(380px, 56vh, 560px)",
        display: "flex", flexDirection: "column", justifyContent: "flex-end",
      }}>
        <div className="t-eyebrow" style={{ marginBottom: 14 }}>
          Analyse d&apos;annonces immobilières · Metz &amp; Moselle
        </div>
        <h1 style={{
          fontFamily: "var(--font-serif)",
          fontSize: "clamp(34px, 5.2vw, 56px)",
          lineHeight: 1.04,
          letterSpacing: "-0.02em",
          color: "var(--ink)",
          margin: "0 0 16px",
          fontWeight: 400,
          maxWidth: 640,
        }}>
          Ce prix et cette annonce sont-ils{" "}
          <em style={{ color: "var(--brick)", fontStyle: "italic" }}>cohérents</em>{" "}
          avec le marché messin, quartier par quartier&nbsp;?
        </h1>
        <p style={{
          fontFamily: "var(--font-sans)",
          fontSize: 17,
          lineHeight: 1.55,
          color: "var(--ink-2)",
          margin: 0,
          maxWidth: 560,
        }}>
          Le livre foncier n&apos;est pas public : impossible de savoir à quel prix
          s&apos;est vraiment vendu le voisin. Nous reconstituons le marché local à
          partir des annonces réelles — du Sablon à Queuleu, de Devant-les-Ponts à
          l&apos;Outre-Seille — et comparons votre annonce, comparable par comparable.
        </p>
      </div>

      {/* Crédit photo (attribution licence) — discret, bas-droite */}
      {HERO_CREDIT && (
        <div style={{
          position: "absolute",
          right: 12,
          bottom: 8,
          fontFamily: "var(--font-sans)",
          fontSize: 11,
          color: "var(--ink-3)",
          opacity: 0.8,
        }}>
          {HERO_CREDIT}
        </div>
      )}
    </section>
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

// Bloc « pourquoi local > national » : le parti pris d'ancrage. Énonce la
// différence d'échelle (ville vs quartier) sans surpromettre — renvoie à la
// page méthode pour le détail.
function LocalEdgeSection() {
  return (
    <div style={{
      paddingTop: 32,
      borderTop: "1px solid var(--stone-line)",
      display: "flex",
      flexDirection: "column",
      gap: 14,
    }}>
      <div className="t-eyebrow">L&apos;ancrage local, notre parti pris</div>
      <div style={{
        fontFamily: "var(--font-serif)",
        fontSize: 24,
        lineHeight: 1.2,
        color: "var(--ink)",
        maxWidth: 560,
      }}>
        Les sites nationaux raisonnent à l&apos;échelle de la ville.
        Nous raisonnons à l&apos;échelle du quartier.
      </div>
      <p style={{
        fontFamily: "var(--font-sans)",
        fontSize: 15,
        lineHeight: 1.6,
        color: "var(--ink-2)",
        margin: 0,
        maxWidth: 560,
      }}>
        Un T3 à Queuleu et un T3 au Sablon n&apos;ont ni le même marché, ni le même
        prix au m². Une médiane à l&apos;échelle de Metz lisse ces écarts et trompe.
        Nous reconstituons le marché à partir des annonces réelles du secteur,
        retenons les comparables à surface proche (±20 %, au moins trois), et
        situons votre annonce dans ce contexte — pas dans une moyenne nationale.
      </p>
      <a href="/methode" style={{
        fontFamily: "var(--font-sans)",
        fontSize: 14,
        fontWeight: 500,
        color: "var(--brick)",
        textDecoration: "none",
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        width: "fit-content",
      }}>
        Notre méthode locale, en détail →
      </a>
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
      "Cohérence — édition Metz",
      "Analyse de cohérence d'une annonce immobilière · Metz & Moselle",
      "————————————————————————————————————————",
      "",
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

  // Impression → PDF via le navigateur. La feuille @media print masque le
  // chrome (.no-print) et révèle l'en-tête au cachet (.print-only), pour un
  // document propre exploitable par un utilisateur standard (vs un .md brut).
  function handlePrint() {
    if (!result) return;
    window.print();
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

      {appState === "idle" && <HeroBanner />}

      <main style={{
        maxWidth: 720,
        margin: "0 auto",
        padding: appState === "idle" ? "40px 24px 64px" : "48px 24px 64px",
        transition: "padding var(--dur-page) var(--ease-paper)",
      }}>

        {/* ── IDLE ── */}
        {appState === "idle" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 40 }}>
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
            <LocalEdgeSection />
          </div>
        )}

        {/* ── ANALYZING ── */}
        {appState === "analyzing" && <AnalyzingState />}

        {/* ── RESULT ── */}
        {appState === "result" && result && (
          <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            {/* En-tête « scellé » visible uniquement à l'impression / PDF. */}
            <div className="print-only" style={{ marginBottom: 8 }}>
              <LorraineSeal size={56} style={{ color: "var(--jaumont)", display: "block", marginBottom: 12 }} />
              <div style={{ fontFamily: "var(--font-serif)", fontSize: 28, color: "var(--ink)", lineHeight: 1.1 }}>
                Cohérence <span style={{ color: "var(--ink-3)" }}>— édition Metz</span>
              </div>
              <div style={{ fontFamily: "var(--font-sans)", fontSize: 13, color: "var(--ink-3)", marginTop: 4 }}>
                Analyse de cohérence d&apos;une annonce · Metz &amp; Moselle ·{" "}
                {new Date().toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })}
              </div>
              <div style={{ borderBottom: "1px solid var(--stone-line)", marginTop: 12 }} />
            </div>

            {/* Action bar */}
            <div className="no-print" style={{
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
              <button onClick={handlePrint} aria-label="Imprimer ou enregistrer le rapport en PDF" style={{
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
                <Printer size={14} />
                Imprimer / PDF
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
                  <div className="no-print" style={{
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

              <div className="no-print" style={{
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
            <div className="no-print">
              <FeedbackForm sent={feedbackSent} onSubmit={handleFeedback} />
            </div>
          </div>
        )}

        <div className="no-print">
          <Footer />
        </div>
      </main>
    </div>
  );
}
