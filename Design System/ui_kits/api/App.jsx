// App — Cohérence API reference page.

const REQUEST_EXAMPLE = `{
  "raw_text": "Bel appartement T3 en plein cœur de Metz, 68,5 m², refait à neuf, 232 000 €, charges 145 €/mois…",
  "source_url": "https://laveine.immo/annonce/3-pieces-metz-centre-8742"
}`;

const RESPONSE_EXAMPLE = `{
  "score": 73,
  "verdict": "À\u00a0creuser",
  "summary": "Le prix est 18 % au-dessus de la médiane locale.",
  "pillars": {
    "price": {
      "points": 25,
      "max": 40,
      "median_price_m2": 3420,
      "q1": 3310, "q3": 3510,
      "position": "Légèrement sur-positionné",
      "delta_pct": 18,
      "confidence": "MOYENNE",
      "comparables_count": 4
    },
    "semantic": {
      "points": 48,
      "max": 60,
      "verdict": "BON",
      "risk_level": "MODÉRÉ",
      "to_check": [
        "Année de construction non mentionnée",
        "Charges de copropriété absentes"
      ],
      "questions": [
        "Depuis combien de temps le bien est-il en vente ?",
        "Y a-t-il eu une baisse de prix ?"
      ],
      "negotiation_levers": [
        "18 % au-dessus de la médiane locale.",
        "DPE non communiqué dans l'annonce."
      ]
    }
  }
}`;

const APIWordmark = ({ size = 22 }) => (
  <a href="#" style={{ display: "inline-flex", alignItems: "center", gap: 10, textDecoration: "none", color: "var(--ink)", whiteSpace: "nowrap" }}>
    <svg width={size} height={size} viewBox="0 0 64 64" style={{ flexShrink: 0 }}>
      <path d="M32 6 L58 32 L32 58 L6 32 Z" fill="var(--brick)" />
      <path d="M32 20 L44 32 L32 44 L20 32 Z" fill="var(--parchment)" />
    </svg>
    <span style={{ fontFamily: "var(--font-serif)", fontSize: size * 0.95, lineHeight: 1, letterSpacing: "-0.02em", color: "var(--ink)" }}>Cohérence</span>
    <span style={{
      marginLeft: 4, padding: "2px 7px",
      background: "var(--stone-fill)", color: "var(--ink-3)",
      fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.06em", textTransform: "uppercase",
      borderRadius: 2, whiteSpace: "nowrap",
    }}>API · v1</span>
  </a>
);

const App = () => {
  const [busy, setBusy] = React.useState(false);
  const [response, setResponse] = React.useState(RESPONSE_EXAMPLE);
  const [requestBody, setRequestBody] = React.useState(REQUEST_EXAMPLE);

  const send = () => {
    setBusy(true);
    setTimeout(() => { setResponse(RESPONSE_EXAMPLE); setBusy(false); }, 900);
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--parchment)", color: "var(--ink)" }}>
      <header style={{
        position: "sticky", top: 0, zIndex: 10,
        backdropFilter: "blur(8px)",
        background: "color-mix(in oklab, var(--parchment), transparent 20%)",
        borderBottom: "1px solid var(--stone-line)",
      }}>
        <div style={{
          maxWidth: 1100, margin: "0 auto",
          padding: "14px 32px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <APIWordmark />
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "5px 10px",
            border: "1px solid var(--stone-line)", borderRadius: 999,
            background: "var(--paper)",
            fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--ink-3)",
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--moss)", display: "inline-block" }} />
            api.coherence.immo
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "48px 32px 96px" }}>
        <div style={{ marginBottom: 32 }}>
          <div className="t-eyebrow" style={{ marginBottom: 14 }}>Référence API · MVP</div>
          <h1 style={{
            fontFamily: "var(--font-serif)", fontSize: 36, lineHeight: 1.05,
            letterSpacing: "-0.02em", color: "var(--ink)", margin: 0, fontWeight: 400,
            maxWidth: 640,
          }}>
            Un seul point d'entrée. Une seule réponse JSON.<br/>
            <em style={{ color: "var(--brick)", fontStyle: "italic" }}>Aucune surface client</em> en dehors de celui-ci.
          </h1>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 32, alignItems: "flex-start" }}>
          {/* Main column */}
          <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
            <EndpointHeader
              method="POST"
              path="/analyze"
              description="Analyse la cohérence d'une annonce immobilière (URL ou texte brut) contre la base de comparables locaux. Retourne un score 0 – 100, un verdict, et deux piliers détaillés."
            />

            <section>
              <h2 style={{ fontFamily: "var(--font-serif)", fontSize: 24, color: "var(--ink)", margin: "0 0 16px", fontWeight: 400 }}>
                Corps de la requête
              </h2>
              <div style={{
                background: "var(--paper)", border: "1px solid var(--stone-line)",
                borderRadius: 4, padding: "20px 22px", marginBottom: 16,
              }}>
                <SchemaTable rows={[
                  { name: "raw_text", type: "string", required: true, description: "Texte brut de l'annonce. Au moins 40 caractères. Utiliser ce champ si l'URL n'est pas accessible." },
                  { name: "source_url", type: "string · url", description: "URL canonique de l'annonce (optionnel). Si fourni, sert d'identifiant pour le cache LLM." },
                ]} />
              </div>
              <textarea
                value={requestBody}
                onChange={(e) => setRequestBody(e.target.value)}
                rows={6}
                style={{
                  width: "100%", padding: "14px 16px",
                  background: "var(--ink)", color: "var(--parchment)",
                  border: "1px solid var(--stone-line)", borderRadius: 4,
                  fontFamily: "var(--font-mono)", fontSize: 13, lineHeight: 1.55,
                  resize: "vertical", outline: "none",
                }}
              />
              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 14 }}>
                <button onClick={send} style={{
                  display: "inline-flex", alignItems: "center", gap: 8,
                  padding: "11px 18px", background: "var(--brick)", color: "var(--parchment)",
                  border: "none", borderRadius: 4,
                  fontFamily: "var(--font-sans)", fontSize: 14, fontWeight: 500, lineHeight: 1,
                  cursor: "pointer",
                }}>
                  {busy ? "Envoi…" : "Envoyer la requête →"}
                </button>
              </div>
            </section>

            <section>
              <h2 style={{ fontFamily: "var(--font-serif)", fontSize: 24, color: "var(--ink)", margin: "0 0 16px", fontWeight: 400 }}>
                Réponse · 200&nbsp;OK
              </h2>
              <div style={{
                background: "var(--paper)", border: "1px solid var(--stone-line)",
                borderRadius: 4, padding: "20px 22px", marginBottom: 16,
              }}>
                <SchemaTable rows={[
                  { name: "score", type: "integer · 0 – 100", required: true, description: "Score global de cohérence." },
                  { name: "verdict", type: "enum", required: true, description: "Verdict synthétique.", enum: ["Favorable", "À\u00a0creuser", "Prudence", "Déconseillé"] },
                  { name: "summary", type: "string", description: "Une phrase, formulée en vouvoiement." },
                  { name: "pillars.price", type: "object", description: "Détail du pilier prix : médiane, position, écart, confiance." },
                  { name: "pillars.semantic", type: "object", description: "Détail du pilier sémantique : verdict LLM, niveau de risque, listes à vérifier." },
                ]} />
              </div>
              <JsonBlock title="Exemple · 200 OK" data={response} />
            </section>
          </div>

          {/* Side rail */}
          <aside style={{ display: "flex", flexDirection: "column", gap: 20, position: "sticky", top: 88 }}>
            <EnvList items={[
              { name: "OPENAI_API_KEY", platform: "Railway", description: "Clé pour gpt-4.1-mini, JSON mode, temp 0.2." },
              { name: "NEXT_PUBLIC_API_URL", platform: "Vercel", description: "URL publique de l'API Railway." },
            ]} />
            <RubricCard />
            <div style={{
              background: "var(--stone-fill)", border: "1px solid var(--stone-line)",
              borderRadius: 4, padding: "16px 18px",
            }}>
              <div className="t-eyebrow" style={{ marginBottom: 10 }}>Périmètre MVP</div>
              <ul style={{ margin: 0, paddingLeft: 18, fontFamily: "var(--font-sans)", fontSize: 12, color: "var(--ink-2)", lineHeight: 1.6 }}>
                <li>Géographie : Metz / Moselle uniquement</li>
                <li>Pas d'estimation de prix, pas de DVF</li>
                <li>Cache LLM mémoire · TTL 7&nbsp;j</li>
                <li>SQLite, pas de migrations</li>
                <li>Validation manuelle via Swagger <code style={{ fontFamily: "var(--font-mono)" }}>/docs</code></li>
              </ul>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
};

Object.assign(window, { App });
