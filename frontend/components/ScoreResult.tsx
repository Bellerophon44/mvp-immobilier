function scoreColor(score: number): string {
  if (score >= 70) return "var(--good)";
  if (score >= 50) return "var(--warn)";
  return "var(--bad)";
}

export default function ScoreResult({ result }: any) {
  const score = Math.max(0, Math.min(100, Number(result.global_score) || 0));
  const color = scoreColor(score);

  return (
    <div
      className="score-card"
      style={
        {
          ["--score-pct" as any]: score,
          ["--score-color" as any]: color,
        } as React.CSSProperties
      }
    >
      <div className="score-ring">
        <div className="score-ring-inner">
          <div className="score-value">{score}</div>
          <span className="score-max">sur 100</span>
        </div>
      </div>
      <div>
        <p className="score-meta-eyebrow">Score de cohérence</p>
        <h2 className="score-verdict">{result.verdict}</h2>
        <p className="score-confidence">
          Confiance dans l'analyse : <strong>{result.confidence}</strong>
        </p>
      </div>
    </div>
  );
}
