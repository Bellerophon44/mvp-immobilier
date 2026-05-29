// RubricCard — the scoring rubric, brand-styled.

const RubricCard = () => (
  <div style={{
    background: "var(--paper)",
    border: "1px solid var(--stone-line)",
    borderRadius: 4,
    padding: "18px 20px",
  }}>
    <div className="t-eyebrow" style={{ marginBottom: 14 }}>Rubrique de scoring</div>
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <div style={{ fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 600, color: "var(--ink)", marginBottom: 6 }}>
          Pilier prix <span style={{ color: "var(--stone)", fontFamily: "var(--font-mono)", fontWeight: 400, fontSize: 12 }}>40 pts</span>
        </div>
        <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 4 }}>
          {[
            ["Aligné (±10\u00a0%)", "35"],
            ["Légèrement sur-positionné (+10 – 25\u00a0%)", "25"],
            ["Fortement sur-positionné (>+25\u00a0%)", "10"],
            ["Sous-positionné (<−10\u00a0%)", "30"],
          ].map(([l, v]) => (
            <li key={l} style={{
              display: "flex", justifyContent: "space-between", alignItems: "baseline",
              gap: 12,
              fontFamily: "var(--font-sans)", fontSize: 12, color: "var(--ink-2)",
              paddingBottom: 4, borderBottom: "1px dotted var(--stone-line)",
            }}>
              <span>{l}</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--ink)", fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>{v} pts</span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <div style={{ fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 600, color: "var(--ink)", marginBottom: 6 }}>
          Verdict final <span style={{ color: "var(--stone)", fontFamily: "var(--font-mono)", fontWeight: 400, fontSize: 12 }}>0 – 100</span>
        </div>
        <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 4 }}>
          {[
            ["75 – 100", "Favorable", "var(--moss)"],
            ["55 – 74", "À\u00a0creuser", "var(--ochre)"],
            ["35 – 54", "Prudence", "var(--brick)"],
            ["0 – 34", "Déconseillé", "var(--brick-deep)"],
          ].map(([range, label, color]) => (
            <li key={range} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              fontFamily: "var(--font-sans)", fontSize: 12,
              paddingBottom: 4, borderBottom: "1px dotted var(--stone-line)",
            }}>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--ink-3)", fontVariantNumeric: "tabular-nums" }}>{range}</span>
              <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: 14, color }}>{label}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  </div>
);

Object.assign(window, { RubricCard });
