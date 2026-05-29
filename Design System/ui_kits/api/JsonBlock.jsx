// JsonBlock — JSON-flavored monospaced block, brand-coloured.

const tokenize = (json) => {
  // Cheap, deterministic JSON colorizer for display only.
  const safe = json
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return safe.replace(
    /("(?:\\.|[^"\\])*"\s*:)|("(?:\\.|[^"\\])*")|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|\b(true|false|null)\b/g,
    (m, key, str, num, lit) => {
      if (key) return `<span style="color:var(--ink)">${key}</span>`;
      if (str) return `<span style="color:var(--moss)">${str}</span>`;
      if (num) return `<span style="color:var(--brick)">${num}</span>`;
      if (lit) return `<span style="color:var(--ochre)">${lit}</span>`;
      return m;
    }
  );
};

const JsonBlock = ({ data, title }) => {
  const text = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  return (
    <div style={{
      background: "var(--ink)", color: "var(--parchment)",
      borderRadius: 4, overflow: "hidden",
    }}>
      {title && (
        <div style={{
          padding: "10px 16px",
          borderBottom: "1px solid rgba(245,241,234,0.08)",
          fontFamily: "var(--font-mono)", fontSize: 11,
          letterSpacing: "0.06em", textTransform: "uppercase",
          color: "var(--stone-line)",
        }}>{title}</div>
      )}
      <pre style={{
        margin: 0, padding: "16px 20px",
        fontFamily: "var(--font-mono)", fontSize: 13, lineHeight: 1.55,
        whiteSpace: "pre", overflow: "auto", color: "var(--stone-line)",
      }}>
        <code dangerouslySetInnerHTML={{ __html: tokenize(text) }} />
      </pre>
    </div>
  );
};

Object.assign(window, { JsonBlock });
