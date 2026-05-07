export default function ScoreResult({ result }: any) {
  return (
    <div>
      <h2>Score de cohérence</h2>
      <p><strong>{result.global_score} / 100</strong></p>
      <p>{result.verdict}</p>
      <p>Confiance : {result.confidence}</p>
    </div>
  );
}
