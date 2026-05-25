type Tone = "good" | "warn" | "bad" | "neutral";

function verdictTone(verdict: string, label: string): Tone {
  const v = (verdict || "").toLowerCase();
  const l = (label || "").toLowerCase();

  if (v.includes("indétermin")) return "neutral";

  if (
    v.includes("bonne") ||
    v.includes("aligné") ||
    v.includes("sous") ||
    v.includes("cohérence forte")
  ) {
    return "good";
  }

  if (v === "faible") {
    return l.includes("risque") ? "good" : "bad";
  }

  if (
    v.includes("élevé") ||
    v.includes("fortement") ||
    v.includes("cohérence faible")
  ) {
    return "bad";
  }

  if (
    v.includes("moyenne") ||
    v.includes("modéré") ||
    v.includes("légèrement") ||
    v.includes("creuser")
  ) {
    return "warn";
  }

  return "neutral";
}

export default function Pillars({ pillars }: any) {
  return (
    <div className="pillars-grid">
      {pillars.map((p: any) => {
        const tone = verdictTone(p.verdict, p.label);
        return (
          <div key={p.label} className="pillar-card">
            <div className="pillar-label">{p.label}</div>
            <span className={`verdict-badge tone-${tone}`}>{p.verdict}</span>
            <p className="pillar-explanation">{p.explanation}</p>
          </div>
        );
      })}
    </div>
  );
}
