export interface Lever {
  quote: string;
  note?: string;
}

interface LeversListProps {
  items: Lever[];
}

export default function LeversList({ items }: LeversListProps) {
  if (!items.length) return null;
  return (
    <div style={{
      background: "var(--paper)",
      border: "1px solid var(--stone-line)",
      borderRadius: 4,
      padding: "20px 22px",
    }}>
      <div className="t-eyebrow" style={{ marginBottom: 14 }}>Leviers de négociation</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {items.map((it, i) => (
          <div key={i} style={{ display: "flex", gap: 14 }}>
            <div style={{ width: 2, background: "var(--brick)", flexShrink: 0, borderRadius: 1 }} />
            <div>
              <div className="t-quote" style={{ fontSize: 18, color: "var(--ink)" }}>
                «&nbsp;{it.quote}&nbsp;»
              </div>
              {it.note && (
                <div style={{ fontFamily: "var(--font-sans)", fontSize: 12, color: "var(--stone)", marginTop: 4 }}>
                  {it.note}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
