export default function Actions({ actions }: any) {
  return (
    <div>
      <h3>Que faire maintenant ?</h3>

      <h4>À vérifier</h4>
      <ul>{actions.check.map((c: string) => <li key={c}>{c}</li>)}</ul>

      <h4>Questions à poser</h4>
      <ul>{actions.questions.map((q: string) => <li key={q}>{q}</li>)}</ul>

      <h4>Leviers de discussion</h4>
      <ul>{actions.negotiation.map((n: string) => <li key={n}>{n}</li>)}</ul>
    </div>
  );
}
