"use client";

import { useEffect, useRef, useState } from "react";
import { analyzeListing, sendEvent, sendFeedback, ApiResult, LocalContext } from "../lib/api";
import AnalyzerInput, { AnalyzerMode } from "../components/design/AnalyzerInput";
import VerdictHeader from "../components/design/VerdictHeader";
import PillarBar from "../components/design/PillarBar";
import ChecklistCard from "../components/design/ChecklistCard";
import LeversList from "../components/design/LeversList";
import Wordmark from "../components/design/Wordmark";
import ScopeBadge from "../components/design/ScopeBadge";
import Footer from "../components/design/Footer";
import FeedbackForm from "../components/design/FeedbackForm";
import { Copy, Printer, MapPin, Seal, AlerionMark } from "../components/design/Icons";
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

// Bande de score (proxy de funnel, jamais le score exact) pour l'event
// analysis_succeeded. Bornes alignees sur le verdict global backend.
function scoreBand(score: number): "lt40" | "40_59" | "60_79" | "80plus" {
  if (score >= 80) return "80plus";
  if (score >= 60) return "60_79";
  if (score >= 40) return "40_59";
  return "lt40";
}

// Statut du pilier prix derive du verdict textuel vers l'enum fermee de /events
// (jamais le verdict brut). "Indeterminé" / inconnu -> indetermine.
function pillarPriceStatus(
  verdict: string | undefined,
): "aligne" | "sous" | "leger_sur" | "fort_sur" | "indetermine" {
  const v = (verdict || "").toLowerCase();
  if (v.includes("aligné")) return "aligne";
  if (v.includes("sous")) return "sous";
  if (v.includes("légèrement")) return "leger_sur";
  if (v.includes("fortement") || v.includes("fort")) return "fort_sur";
  return "indetermine";
}

// Mappe le scope du pilier prix (quartier/secteur/ville/metropole/null) vers
// l'enum fermee from_scope/to_scope de /events. null/inconnu -> indetermine.
function scopeDimension(
  scope: ApiResult["pillars"][number]["scope"] | undefined,
): "quartier" | "secteur" | "ville" | "metropole" | "indetermine" {
  if (scope === "quartier" || scope === "secteur" || scope === "ville" || scope === "metropole") {
    return scope;
  }
  return "indetermine";
}

// Mappe une erreur d'analyse vers l'enum fermee reason (jamais le message brut).
// Le backend renvoie 422 quand l'URL est injoignable ; faute d'entree -> no_input.
function failureReason(message: string): "url_unreachable" | "no_input" {
  const m = message.toLowerCase();
  if (m.includes("url") || m.includes("récupérer") || m.includes("recuperer")) {
    return "url_unreachable";
  }
  return "no_input";
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
const HERO_IMAGE: string | null = "/hero-metz.jpg";
const HERO_ALT = "La Porte des Allemands et le pont sur la Seille, à Metz";

// Grain argentique discret (SVG feTurbulence en data-URI), posé en multiply.
const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")";

// Bande de preuve chiffrée — mécanisme « trois signaux above-the-fold » (cf.
// docs/strategy/REBRAND-2026.md). On n'affiche QUE des chiffres vrais de
// méthode/donnée (jamais de traction : pas de logos clients, pas de note, pas de
// « milliers d'acheteurs »). L'or Jaumont devient la couleur de la donnée.
// À RECONFIRMER avant promotion prod : « 16 quartiers » = frontend/lib/districts.ts ;
// « 17 000+ » = plancher de la base prod (~17,7k, CONTEXT.md §0) ; « 7 j » =
// collecte hebdomadaire (collect.yml). Idéalement brancher sur un endpoint de
// comptage pour que ces chiffres ne se périment pas.
const PROOF_POINTS: { num: string; label: string }[] = [
  { num: "17 000+", label: "comparables messins en base" },
  { num: "16", label: "quartiers de Metz couverts" },
  { num: "7 j", label: "données rafraîchies chaque semaine" },
];

function ProofBand() {
  return (
    <div>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        borderTop: "1px solid var(--stone-line)",
        borderBottom: "1px solid var(--stone-line)",
      }}>
        {PROOF_POINTS.map((p, i) => (
          <div key={p.num} style={{
            padding: "18px 8px",
            textAlign: "center",
            borderLeft: i === 0 ? "none" : "1px solid var(--stone-line)",
          }}>
            <div style={{
              fontFamily: "var(--font-mono)",
              fontWeight: 600,
              fontSize: "clamp(20px, 6vw, 30px)",
              lineHeight: 1,
              letterSpacing: "-0.02em",
              color: "var(--jaumont)",
            }}>
              {p.num}
            </div>
            <div style={{
              fontFamily: "var(--font-sans)",
              fontSize: 12,
              color: "var(--ink-3)",
              lineHeight: 1.35,
              marginTop: 8,
            }}>
              {p.label}
            </div>
          </div>
        ))}
      </div>
      <p style={{
        fontFamily: "var(--font-serif)",
        fontStyle: "italic",
        fontSize: 18,
        color: "var(--ink-2)",
        lineHeight: 1.35,
        margin: "16px 0 0",
        textAlign: "center",
      }}>
        Nous vérifions une cohérence. Nous n&apos;estimons pas un prix.
      </p>
    </div>
  );
}

// Bande signature « édition Metz » — image d'ambiance N&B chaude, encadrée et
// posée EN BAS de la home (plus jamais avant le titre, en particulier sur mobile
// où elle mangeait le premier écran). C'est une respiration éditoriale, pas un
// sujet. Traitement N&B chaud + grain en CSS ; placeholder pierre si pas d'image.
function SignatureBand() {
  return (
    <div aria-label="Metz" style={{
      position: "relative",
      width: "100%",
      height: "clamp(120px, 17vh, 184px)",
      overflow: "hidden",
      borderRadius: 8,
      border: "1px solid var(--stone-line)",
    }}>
      {HERO_IMAGE ? (
        <img src={HERO_IMAGE} alt={HERO_ALT} style={{
          position: "absolute", inset: 0, width: "100%", height: "100%",
          objectFit: "cover",
          filter: "grayscale(1) sepia(0.32) contrast(1.04) brightness(0.78)",
        }} />
      ) : (
        <div aria-hidden style={{
          position: "absolute", inset: 0,
          background: "radial-gradient(130% 140% at 72% 6%, var(--stone-fill) 0%, var(--paper) 60%, var(--parchment) 100%)",
        }} />
      )}

      {/* Grain argentique */}
      <div aria-hidden style={{
        position: "absolute", inset: 0,
        backgroundImage: GRAIN, backgroundSize: "140px 140px",
        mixBlendMode: "multiply", opacity: 0.10, pointerEvents: "none",
      }} />

      <div style={{
        position: "absolute", left: 14, bottom: 10,
        fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: 15,
        color: "var(--parchment)", textShadow: "0 1px 6px rgba(0,0,0,0.5)",
      }}>
        Metz, pierre de Jaumont
      </div>
    </div>
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

// Screening photo (mode URL) : seuls `confirme` et `non_trouve` ont un rendu ;
// `non_applicable` (et l'absence de statut) ne montrent rien.
const PHOTO_STATUS: Record<string, { color: string; label: string }> = {
  confirme: { color: "var(--moss)", label: "Confirmé par une photo" },
  non_trouve: {
    color: "var(--ochre)",
    label: "Non visible sur les photos de l'annonce — à vérifier en visite",
  },
};

// Bloc "Contexte local" : profil curaté du quartier (couche A) + contrôle de
// cohérence des allégations de l'annonce (couche B). Volontairement non-scoré
// (comme la carte prix). Distances approximatives au niveau du quartier — pas un
// 4e pilier, on garde le score 40/30/30 et "pas de fausse précision".
function LocalContextCard({
  context,
  mode,
}: {
  context: LocalContext;
  mode?: "url" | "text";
}) {
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
                    {c.photo_status && PHOTO_STATUS[c.photo_status] && (
                      <div style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        marginTop: 6,
                        fontFamily: "var(--font-sans)",
                        fontSize: 12,
                        color: PHOTO_STATUS[c.photo_status].color,
                        lineHeight: 1.4,
                      }}>
                        <span style={{
                          flexShrink: 0,
                          width: 7,
                          height: 7,
                          borderRadius: 999,
                          background: PHOTO_STATUS[c.photo_status].color,
                        }} />
                        {PHOTO_STATUS[c.photo_status].label}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {mode === "url" && (
            <div style={{
              marginTop: 12,
              fontFamily: "var(--font-sans)",
              fontSize: 11,
              color: "var(--stone)",
              lineHeight: 1.5,
            }}>
              Les photos de l&apos;annonce sont analysées en transit et ne sont pas conservées.
            </div>
          )}
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
  // Garde anti double-comptage StrictMode (double mount en dev) : page_view
  // n'est emis qu'une fois par montage reel.
  const pageViewSent = useRef(false);

  useEffect(() => {
    if (pageViewSent.current) return;
    pageViewSent.current = true;
    // referrer_domain = hostname SEUL (jamais le referrer brut / path / query).
    let referrerDomain: string | undefined;
    if (document.referrer) {
      try {
        referrerDomain = new URL(document.referrer).hostname;
      } catch {
        referrerDomain = undefined;
      }
    }
    sendEvent("page_view", { path: "/", referrer_domain: referrerDomain });
  }, []);

  async function handleAnalyze({ mode, value }: AnalyzerMode) {
    setAppState("analyzing");
    setError(null);
    setSelectedDistrict("");
    setAddressInput("");
    setLastInput({ mode, value });
    setFeedbackSent(false);
    // Jamais la valeur saisie / l'URL : seul le mode (proxy de funnel).
    sendEvent("analysis_started", { mode });
    try {
      const res = await analyzeListing(value, mode);
      setResult(res);
      setAnalysisId(crypto.randomUUID());
      setAppState("result");
      sendEvent("analysis_succeeded", {
        score_band: scoreBand(res.global_score),
        confidence: res.confidence,
        pillar_price_status: pillarPriceStatus(res.pillars[0]?.verdict),
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur lors de l'analyse.";
      setError(msg);
      setAppState("idle");
      sendEvent("analysis_failed", { reason: failureReason(msg) });
    }
  }

  // Ré-analyse affinée : par quartier (#6-A, pilier prix) et/ou par adresse
  // saisie (feedback local, alternative manuelle au géocodage).
  async function handleRefine(district: string, address: string) {
    if (!lastInput || (!district && !address.trim())) return;
    setRefining(true);
    setError(null);
    setFeedbackSent(false);
    // Scope du pilier prix AVANT la ré-analyse (district_refine n'est pas
    // analysis_started : un affinage ne doit pas fausser le taux de lancement).
    const fromScope = scopeDimension(result?.pillars[0]?.scope);
    try {
      const res = await analyzeListing(lastInput.value, lastInput.mode, district, address);
      setResult(res);
      setAnalysisId(crypto.randomUUID());
      sendEvent("district_refine", {
        from_scope: fromScope,
        to_scope: scopeDimension(res.pillars[0]?.scope),
      });
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
    // Booléen de présence seulement, jamais la chaîne d'adresse.
    sendEvent("address_entered", { address_entered: Boolean(addressInput.trim()) });
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
    sendEvent("report_export", { format: "copy" });
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
    sendEvent("report_export", { format: "pdf" });
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

      <main style={{
        maxWidth: 720,
        margin: "0 auto",
        padding: appState === "idle" ? "48px 24px 64px" : "48px 24px 64px",
        transition: "padding var(--dur-page) var(--ease-paper)",
      }}>

        {/* ── IDLE ── */}
        {appState === "idle" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 40 }}>
            <div>
              {/* Marque « édition Metz » : l'alérion lorrain unique (aiglon de
                  Lorraine, sans bec ni pattes), en letterhead sur parchemin, encré
                  en or Jaumont. Lisible — contrairement au cachet aux trois alérions. */}
              <AlerionMark size={72} style={{ color: "var(--jaumont)", marginBottom: 24, display: "block" }} />
              <div className="t-eyebrow" style={{ marginBottom: 16 }}>
                Édition Metz · Moselle
              </div>
              <h1 style={{
                fontFamily: "var(--font-serif)",
                fontSize: "clamp(34px, 8vw, 56px)",
                lineHeight: 1.04,
                letterSpacing: "-0.02em",
                color: "var(--ink)",
                margin: "0 0 18px",
                fontWeight: 400,
                maxWidth: 620,
              }}>
                Le marché immobilier messin, lu{" "}
                <em style={{ color: "var(--brick)", fontStyle: "italic" }}>quartier par quartier</em>.
              </h1>
              <p style={{
                fontFamily: "var(--font-sans)",
                fontSize: 17,
                lineHeight: 1.55,
                color: "var(--ink-2)",
                margin: 0,
                maxWidth: 540,
              }}>
                Le livre foncier n&apos;est pas public. Nous reconstituons le marché
                messin à partir des annonces réelles — du Sablon à Queuleu, de
                Devant-les-Ponts à l&apos;Outre-Seille — et plaçons la vôtre dans ce
                contexte&nbsp;: score de cohérence, trois piliers de lecture, et les
                points à vérifier avant la visite.
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

            <ProofBand />
            <SecondaryRow />
            <LocalEdgeSection />
            <SignatureBand />
          </div>
        )}

        {/* ── ANALYZING ── */}
        {appState === "analyzing" && <AnalyzingState />}

        {/* ── RESULT ── */}
        {appState === "result" && result && (
          <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            {/* En-tête « scellé » visible uniquement à l'impression / PDF. */}
            <div className="print-only" style={{ marginBottom: 8 }}>
              <AlerionMark size={48} style={{ color: "var(--jaumont)", display: "block", marginBottom: 12 }} />
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
                <LocalContextCard
                  context={result.local_context}
                  mode={lastInput?.mode}
                />
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
