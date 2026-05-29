// EnvList — environment variables with platform chip.

const EnvList = ({ items }) => (
  <div style={{
    background: "var(--paper)",
    border: "1px solid var(--stone-line)",
    borderRadius: 4,
    padding: "18px 20px",
  }}>
    <div className="t-eyebrow" style={{ marginBottom: 14 }}>Variables d'environnement</div>
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {items.map((it) => (
        <div key={it.name} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <code style={{
              fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--ink)", fontWeight: 500,
            }}>{it.name}</code>
            <span style={{
              padding: "1px 6px", borderRadius: 2,
              background: "var(--stone-fill)",
              fontFamily: "var(--font-mono)", fontSize: 10,
              color: "var(--ink-3)", letterSpacing: "0.04em", textTransform: "uppercase",
            }}>{it.platform}</span>
          </div>
          <div style={{ fontFamily: "var(--font-sans)", fontSize: 12, color: "var(--ink-3)", lineHeight: 1.5 }}>
            {it.description}
          </div>
        </div>
      ))}
    </div>
  </div>
);

Object.assign(window, { EnvList });
