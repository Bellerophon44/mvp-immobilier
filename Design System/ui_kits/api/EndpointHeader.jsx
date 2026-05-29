// EndpointHeader — method + path + one-line description.

const EndpointHeader = ({ method, path, description }) => (
  <div style={{
    background: "var(--paper)",
    border: "1px solid var(--stone-line)",
    borderRadius: 4,
    padding: "18px 22px",
    display: "flex", flexDirection: "column", gap: 10,
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <MethodPill method={method} />
      <code style={{
        fontFamily: "var(--font-mono)", fontSize: 17,
        color: "var(--ink)", letterSpacing: "-0.01em",
      }}>{path}</code>
    </div>
    <p style={{
      margin: 0,
      fontFamily: "var(--font-sans)", fontSize: 14, lineHeight: 1.5, color: "var(--ink-3)",
    }}>{description}</p>
  </div>
);

Object.assign(window, { EndpointHeader });
