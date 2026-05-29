// App — the single-page analyzer. Idle → Analyzing → Result.

const MOCK_RESULT = {
  score: 73,
  verdictSummary:
    "Le prix est 18\u00a0% au-dessus de la médiane locale pour cette surface. L'annonce est claire mais omet deux points à vérifier avant la visite.",
  pricePillar: {
    score: 25, max: 40, deltaPct: 18,
    legend: "Légèrement sur-positionné",
  },
  semanticPillar: {
    score: 48, max: 60,
    legend: "Annonce claire, risque modéré. Deux points restent à vérifier.",
  },
  toCheck: [
    { title: "Année de construction non mentionnée", hint: "Demander DPE complet et année exacte avant la visite." },
    { title: "Charges de copropriété absentes", hint: "Demander les trois derniers PV d'assemblée générale." },
    { title: "Surface Carrez clairement indiquée", hint: "68,5\u00a0m² — cohérent avec le plan joint.", done: true },
    { title: "Étage et exposition précisés", hint: "3ᵉ étage, plein sud.", done: true },
  ],
  questions: [
    { title: "Depuis combien de temps le bien est-il en vente\u00a0?", hint: "Permet d'évaluer la marge de négociation." },
    { title: "Y a-t-il eu une baisse de prix depuis la mise en ligne\u00a0?" },
    { title: "Le vendeur est-il pressé de conclure\u00a0?" },
  ],
  comparables: [
    { district: "Sablon", surface: 71, pricePerM2: 3380, delta: -1.2 },
    { district: "Nouvelle Ville", surface: 66, pricePerM2: 3510, delta: 2.6 },
    { district: "Centre", surface: 69, pricePerM2: 3420, delta: 0 },
    { district: "Outre-Seille", surface: 72, pricePerM2: 3310, delta: -3.2 },
  ],
  levers: [
    { quote: "Le bien est 18\u00a0% au-dessus de la médiane de quatre comparables sur le secteur Centre.", note: "Argument principal de négociation." },
    { quote: "DPE non communiqué — la loi impose qu'il figure dans l'annonce.", note: "Point bloquant légitime à soulever." },
  ],
};

const App = () => {
  const [state, setState] = React.useState("idle");           // idle | analyzing | result
  const [pillarsVisible, setPillarsVisible] = React.useState(false);

  const start = ({ mode, value }) => {
    setState("analyzing");
    setTimeout(() => {
      setState("result");
      setTimeout(() => setPillarsVisible(true), 250);
    }, 1400);
  };

  const reset = () => {
    setState("idle");
    setPillarsVisible(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--parchment)", color: "var(--ink)" }}>
      {/* Sticky top bar */}
      <header style={{
        position: "sticky", top: 0, zIndex: 10,
        backdropFilter: "blur(8px)",
        background: "color-mix(in oklab, var(--parchment), transparent 20%)",
        borderBottom: "1px solid var(--stone-line)",
      }}>
        <div style={{
          maxWidth: 960, margin: "0 auto",
          padding: "14px 24px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <Wordmark size={22} />
          <ScopeBadge />
        </div>
      </header>

      <main style={{
        maxWidth: 720, margin: "0 auto",
        padding: state === "idle" ? "96px 24px 64px" : "48px 24px 64px",
        transition: "padding var(--dur-page) var(--ease-paper)",
      }}>
        {state === "idle" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 40 }}>
            <div>
              <div className="t-eyebrow" style={{ marginBottom: 16 }}>Analyseur de cohérence d'annonces</div>
              <h1 style={{
                fontFamily: "var(--font-serif)", fontSize: 56, lineHeight: 1.02,
                letterSpacing: "-0.02em", color: "var(--ink)", margin: 0, fontWeight: 400,
                maxWidth: 620,
              }}>
                Ce prix et cette annonce<br/>
                sont-ils <em style={{ color: "var(--brick)", fontStyle: "italic" }}>cohérents</em> avec<br/>
                le marché local&nbsp;?
              </h1>
              <p style={{
                fontFamily: "var(--font-sans)", fontSize: 17, lineHeight: 1.55,
                color: "var(--ink-2)", marginTop: 18, maxWidth: 540,
              }}>
                Collez l'URL ou le texte d'une annonce. Nous renvoyons un score de cohérence,
                trois piliers de lecture, et une liste de points à vérifier avant la visite.
              </p>
            </div>
            <AnalyzerInput onAnalyze={start} />
            <SecondaryRow />
          </div>
        )}

        {state === "analyzing" && (
          <AnalyzingState />
        )}

        {state === "result" && (
          <ResultView data={MOCK_RESULT} pillarsVisible={pillarsVisible} onReset={reset} />
        )}

        <Footer />
      </main>
    </div>
  );
};

const SecondaryRow = () => (
  <div style={{
    display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12,
    paddingTop: 32, borderTop: "1px solid var(--stone-line)",
  }}>
    {[
      { n: "01", t: "Pilier prix", d: "Médiane locale et écart calculés sur ≥ 3 comparables." },
      { n: "02", t: "Pilier sémantique", d: "L'annonce est-elle claire ? Quels signaux manquent ?" },
      { n: "03", t: "Pilier global", d: "Score 0 – 100 et verdict en une phrase." },
    ].map((c) => (
      <div key={c.n}>
        <div style={{
          fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--stone)",
          letterSpacing: "0.06em", marginBottom: 8,
        }}>{c.n}</div>
        <div style={{
          fontFamily: "var(--font-serif)", fontSize: 20, color: "var(--ink)",
          lineHeight: 1.15, marginBottom: 6,
        }}>{c.t}</div>
        <div style={{
          fontFamily: "var(--font-sans)", fontSize: 13, color: "var(--ink-3)",
          lineHeight: 1.5,
        }}>{c.d}</div>
      </div>
    ))}
  </div>
);

const AnalyzingState = () => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "96px 0", gap: 28 }}>
    <div style={{ width: 132, height: 132, position: "relative" }}>
      <svg width="132" height="132" viewBox="0 0 132 132" style={{ animation: "rotate 1.6s linear infinite" }}>
        <circle cx="66" cy="66" r="54" fill="none" stroke="var(--stone-line)" strokeWidth="6" />
        <circle cx="66" cy="66" r="54" fill="none" stroke="var(--brick)" strokeWidth="6"
          strokeDasharray="339.3" strokeDashoffset="240" strokeLinecap="round" />
      </svg>
    </div>
    <div style={{ textAlign: "center" }}>
      <div className="t-eyebrow" style={{ marginBottom: 8 }}>Analyse en cours</div>
      <div style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: 24, color: "var(--ink-2)" }}>
        Lecture de l'annonce, comparables locaux, calcul du score…
      </div>
    </div>
    <style>{`@keyframes rotate { to { transform: rotate(360deg); } }`}</style>
  </div>
);

const ResultView = ({ data, pillarsVisible, onReset }) => {
  const [copied, setCopied] = React.useState(false);
  const copy = () => { setCopied(true); setTimeout(() => setCopied(false), 1500); };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        paddingBottom: 16, borderBottom: "1px solid var(--stone-line)",
      }}>
        <button onClick={onReset} style={{
          background: "transparent", border: "none", padding: 0, cursor: "pointer",
          fontFamily: "var(--font-sans)", fontSize: 13, color: "var(--ink-3)",
          display: "inline-flex", alignItems: "center", gap: 6, whiteSpace: "nowrap",
        }}>
          ← Analyser une autre annonce
        </button>
        <button onClick={copy} style={{
          display: "inline-flex", alignItems: "center", gap: 8,
          padding: "9px 14px", background: "var(--paper)",
          border: "1px solid var(--stone-line)", borderRadius: 4,
          color: "var(--ink)", fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 500,
          cursor: "pointer", whiteSpace: "nowrap",
        }}>
          <Copy size={14} />
          {copied ? "Rapport copié" : "Copier le rapport"}
        </button>
      </div>

      <VerdictHeader score={data.score} summary={data.verdictSummary} />

      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16,
        opacity: pillarsVisible ? 1 : 0,
        transform: pillarsVisible ? "translateY(0)" : "translateY(8px)",
        transition: "all var(--dur-page) var(--ease-paper)",
      }}>
        <PillarBar
          name="Pilier prix"
          score={data.pricePillar.score}
          max={data.pricePillar.max}
          color="var(--ochre)"
          legend={data.pricePillar.legend}
          deltaPct={data.pricePillar.deltaPct}
        />
        <PillarBar
          name="Pilier sémantique"
          score={data.semanticPillar.score}
          max={data.semanticPillar.max}
          color="var(--moss)"
          legend={data.semanticPillar.legend}
        />
      </div>

      <ChecklistCard eyebrow={"À\u00a0vérifier avant la visite"} items={data.toCheck} />
      <ComparablesTable rows={data.comparables} scope={"Metz · rayon 1,5\u00a0km · surface\u00a0±20\u00a0%"} />
      <ChecklistCard eyebrow="Questions à poser au vendeur" items={data.questions} />
      <LeversList items={data.levers} />
    </div>
  );
};

Object.assign(window, { App });
