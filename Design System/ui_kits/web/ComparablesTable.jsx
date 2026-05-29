// ComparablesTable — the table of retained comparables.

const ComparablesTable = ({ rows, scope }) => (
  <div style={{
    background: "var(--paper)",
    border: "1px solid var(--stone-line)",
    borderRadius: 4,
    padding: "20px 22px",
  }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
      <span className="t-eyebrow">Comparables retenus · {rows.length}</span>
      <span style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        fontFamily: "var(--font-sans)", fontSize: 12, color: "var(--ink-3)",
      }}>
        <MapPin size={14} style={{ color: "var(--stone)" }} />
        {scope}
      </span>
    </div>
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          {["Quartier", "Surface", "€/m²", "Écart"].map((h, i) => (
            <td key={h} style={{
              fontFamily: "var(--font-sans)", fontSize: 11, fontWeight: 500,
              color: "var(--stone)", letterSpacing: "0.04em", textTransform: "uppercase",
              padding: "0 0 8px", borderBottom: "1px solid var(--stone-line)",
              textAlign: i >= 2 ? "right" : "left",
            }}>{h}</td>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => {
          const isMedian = r.delta === 0;
          const upDown = r.delta > 0 ? "var(--brick)" : "var(--moss)";
          return (
            <tr key={i}>
              <td style={{ padding: "10px 0", borderBottom: i === rows.length - 1 ? "none" : "1px solid var(--stone-line)", fontFamily: "var(--font-sans)", fontSize: 14, color: "var(--ink)" }}>
                {r.district}
              </td>
              <td style={{ padding: "10px 0", borderBottom: i === rows.length - 1 ? "none" : "1px solid var(--stone-line)", fontFamily: "var(--font-sans)", fontSize: 14, color: "var(--ink)" }}>
                {r.surface}&nbsp;m²
              </td>
              <td style={{ padding: "10px 0", borderBottom: i === rows.length - 1 ? "none" : "1px solid var(--stone-line)", fontFamily: "var(--font-mono)", fontSize: 14, color: "var(--ink)", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                {r.pricePerM2.toLocaleString("fr-FR")}&nbsp;€
              </td>
              <td style={{
                padding: "10px 0", borderBottom: i === rows.length - 1 ? "none" : "1px solid var(--stone-line)",
                fontFamily: "var(--font-mono)", fontSize: 14, textAlign: "right", fontVariantNumeric: "tabular-nums",
                color: isMedian ? "var(--stone)" : upDown,
              }}>
                {isMedian ? "médiane" : `${r.delta > 0 ? "+" : "−"}${Math.abs(r.delta)}\u00a0%`}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  </div>
);

Object.assign(window, { ComparablesTable });
