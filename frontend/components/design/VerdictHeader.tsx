import ScoreRing, { verdictMeta } from "./ScoreRing";

interface VerdictHeaderProps {
  score: number;
  summary: string;
  confidence?: string;
}

export default function VerdictHeader({ score, summary, confidence }: VerdictHeaderProps) {
  const meta = verdictMeta(score);
  return (
    <div style={{ display: "flex", gap: 28, alignItems: "center", flexWrap: "wrap" }}>
      <ScoreRing score={score} />
      <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1, minWidth: 200 }}>
        <span className="t-eyebrow">Score de cohérence</span>
        <div className={meta.className} style={{
          fontFamily: "var(--font-serif)",
          fontStyle: "italic",
          fontSize: 44,
          lineHeight: 1,
          color: meta.color,
        }}>
          {meta.label}
        </div>
        <div style={{
          fontFamily: "var(--font-sans)",
          fontSize: 15,
          lineHeight: 1.55,
          color: "var(--ink-2)",
          maxWidth: 460,
          marginTop: 4,
        }}>
          {summary}
        </div>
        {confidence && (
          <div style={{ fontFamily: "var(--font-sans)", fontSize: 12, color: "var(--stone)", marginTop: 2 }}>
            Confiance : {confidence}
          </div>
        )}
      </div>
    </div>
  );
}
