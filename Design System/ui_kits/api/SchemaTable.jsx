// SchemaTable — field name · type · description, with optional required marker.

const SchemaTable = ({ title, rows }) => (
  <div>
    {title && <div className="t-eyebrow" style={{ marginBottom: 10 }}>{title}</div>}
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.name}>
            <td style={{
              padding: "12px 16px 12px 0",
              borderBottom: i === rows.length - 1 ? "none" : "1px solid var(--stone-line)",
              verticalAlign: "top", width: "30%",
            }}>
              <div style={{
                fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--ink)", fontWeight: 500,
              }}>
                {r.name}
                {r.required && (
                  <span style={{
                    marginLeft: 6, color: "var(--brick)", fontSize: 11, verticalAlign: "top",
                  }}>•</span>
                )}
              </div>
              <div style={{
                fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--stone)",
                marginTop: 2,
              }}>{r.type}</div>
            </td>
            <td style={{
              padding: "12px 0",
              borderBottom: i === rows.length - 1 ? "none" : "1px solid var(--stone-line)",
              verticalAlign: "top",
              fontFamily: "var(--font-sans)", fontSize: 13, color: "var(--ink-2)", lineHeight: 1.5,
            }}>
              {r.description}
              {r.enum && (
                <div style={{ marginTop: 6, display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {r.enum.map((v) => (
                    <code key={v} style={{
                      fontFamily: "var(--font-mono)", fontSize: 11,
                      padding: "2px 6px",
                      background: "var(--stone-fill)", color: "var(--ink-3)",
                      borderRadius: 2,
                    }}>{v}</code>
                  ))}
                </div>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

Object.assign(window, { SchemaTable });
