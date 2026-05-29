interface WordmarkProps {
  compact?: boolean;
  size?: number;
}

export default function Wordmark({ compact = false, size = 28 }: WordmarkProps) {
  return (
    <a href="/" style={{ display: "inline-flex", alignItems: "center", gap: 10, textDecoration: "none", color: "var(--ink)" }}>
      <svg width={size} height={size} viewBox="0 0 64 64" style={{ flexShrink: 0 }}>
        <path d="M32 6 L58 32 L32 58 L6 32 Z" fill="var(--brick)" />
        <path d="M32 20 L44 32 L32 44 L20 32 Z" fill="var(--parchment)" />
      </svg>
      {!compact && (
        <span style={{
          fontFamily: "var(--font-serif)",
          fontSize: size * 0.95,
          lineHeight: 1,
          letterSpacing: "-0.02em",
          color: "var(--ink)",
        }}>
          Cohérence
        </span>
      )}
    </a>
  );
}
