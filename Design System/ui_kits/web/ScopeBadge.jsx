// ScopeBadge — small "Metz · Moselle" chip with map-pin glyph.

const ScopeBadge = () => (
  <span style={{
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "5px 10px 5px 8px",
    border: "1px solid var(--stone-line)",
    borderRadius: 999,
    background: "var(--paper)",
    color: "var(--ink-3)",
    fontFamily: "var(--font-sans)",
    fontSize: 12,
    lineHeight: 1,
    fontWeight: 500,
  }}>
    <MapPin size={14} style={{ color: "var(--stone)" }} />
    Metz <span style={{ color: "var(--stone)" }}>·</span> Moselle
  </span>
);

Object.assign(window, { ScopeBadge });
