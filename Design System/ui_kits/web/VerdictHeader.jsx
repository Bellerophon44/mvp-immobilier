// VerdictHeader — score ring + verdict label + one-line summary.

const VerdictHeader = ({ score, summary }) => {
  const meta = verdictMeta(score);
  return (
    <div style={{ display: "flex", gap: 28, alignItems: "center" }}>
      <ScoreRing score={score} />
      <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
        <span className="t-eyebrow">Score de cohérence</span>
        <div className={meta.className} style={{
          fontFamily: "var(--font-serif)", fontStyle: "italic",
          fontSize: 44, lineHeight: 1, color: meta.color,
        }}>{meta.label}</div>
        <div style={{
          fontFamily: "var(--font-sans)", fontSize: 15, lineHeight: 1.55,
          color: "var(--ink-2)", maxWidth: 460, marginTop: 4,
        }}>{summary}</div>
      </div>
    </div>
  );
};

Object.assign(window, { VerdictHeader });
