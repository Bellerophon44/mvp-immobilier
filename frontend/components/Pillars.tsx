export default function Pillars({ pillars }: any) {
  return (
    <div>
      <h3>Détail de l’analyse</h3>
      {pillars.map((p: any) => (
        <div key={p.label}>
          <strong>{p.label}</strong>
          <p>{p.verdict}</p>
          <p>{p.explanation}</p>
        </div>
      ))}
    </div>
  );
}
``
