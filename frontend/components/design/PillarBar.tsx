interface PillarBarProps {
  name: string;
  score: number;
  max: number;
  color: string;
  legend: string;
  deltaPct?: number;
}

export default function PillarBar({ name, score, max, color, legend, deltaPct }: PillarBarProps) {
  const pct = Math.min(100, (score / max) * 100);
  return (
    <div style={{
      background: "var(--paper)",
      border: "1px solid var(--stone-line)",
      borderRadius: 4,
      padding: "18px 20px",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
        <span style={{ fontFamily: "var(--font-sans)", fontSize: 14, fontWeight: 600, color: "var(--ink)" }}>
          {name}
        </span>
        <span style={{
          fontFamily: "var(--font-mono)",
          fontSize: 14,
          color: "var(--ink)",
          fontVariantNumeric: "tabular-nums",
          whiteSpace: "nowrap",
        }}>
          {score}<span style={{ color: "var(--stone)" }}>{` / ${max}`}</span>
        </span>
      </div>
      <div style={{ height: 6, background: "var(--stone-fill)", borderRadius: 999, overflow: "hidden" }}>
        <div style={{
          height: "100%",
          width: `${pct}%`,
          background: color,
          borderRadius: 999,
          transition: "width 480ms var(--ease-paper)",
        }} />
      </div>
      <div style={{ fontFamily: "var(--font-sans)", fontSize: 13, color: "var(--ink-3)", lineHeight: 1.5, marginTop: 10 }}>
        {legend}
        {typeof deltaPct === "number" && (
          <>
            {" — "}
            <b style={{ color: "var(--ink)", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontWeight: 500 }}>
              {deltaPct > 0 ? "+" : "−"}{Math.abs(deltaPct)}&nbsp;%
            </b>
            {" vs médiane locale."}
          </>
        )}
      </div>
    </div>
  );
}
