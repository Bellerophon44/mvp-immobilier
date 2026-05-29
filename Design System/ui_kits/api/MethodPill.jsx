// MethodPill — colored tag for HTTP methods. Only POST is brick (the only method we have).

const METHOD_COLORS = {
  GET:    "var(--moss)",
  POST:   "var(--brick)",
  PUT:    "var(--ochre)",
  DELETE: "var(--brick-deep)",
};

const MethodPill = ({ method = "POST" }) => (
  <span style={{
    display: "inline-flex", alignItems: "center",
    padding: "4px 10px",
    background: METHOD_COLORS[method] ?? "var(--stone)",
    color: "var(--parchment)",
    fontFamily: "var(--font-mono)",
    fontSize: 11, fontWeight: 600,
    letterSpacing: "0.06em",
    borderRadius: 2,
    lineHeight: 1.2,
  }}>{method}</span>
);

Object.assign(window, { MethodPill });
