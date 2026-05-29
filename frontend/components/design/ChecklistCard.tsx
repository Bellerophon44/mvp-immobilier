import { SquareCheck } from "./Icons";

export interface ChecklistItem {
  title: string;
  hint?: string;
  done?: boolean;
}

interface ChecklistCardProps {
  eyebrow: string;
  items: ChecklistItem[];
}

export default function ChecklistCard({ eyebrow, items }: ChecklistCardProps) {
  if (!items.length) return null;
  return (
    <div style={{
      background: "var(--paper)",
      border: "1px solid var(--stone-line)",
      borderRadius: 4,
      padding: "20px 22px",
    }}>
      <div className="t-eyebrow" style={{ marginBottom: 12 }}>{eyebrow}</div>
      <div>
        {items.map((it, i) => (
          <div key={i} style={{
            display: "flex",
            gap: 12,
            alignItems: "flex-start",
            padding: "12px 0",
            borderBottom: i === items.length - 1 ? "none" : "1px solid var(--stone-line)",
          }}>
            <span style={{ color: it.done ? "var(--moss)" : "var(--ochre)", flexShrink: 0, marginTop: 1 }}>
              <SquareCheck size={18} checked={!!it.done} />
            </span>
            <div>
              <div style={{ fontFamily: "var(--font-sans)", fontSize: 14, color: "var(--ink)", lineHeight: 1.5 }}>
                {it.title}
              </div>
              {it.hint && (
                <div style={{ fontFamily: "var(--font-sans)", fontSize: 12, color: "var(--ink-3)", lineHeight: 1.5, marginTop: 2 }}>
                  {it.hint}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
