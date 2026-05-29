// ScoreRing — animated 0→score draw on mount. Color follows verdict band.

const verdictMeta = (score) => {
  if (score >= 75) return { label: "Favorable", color: "var(--moss)", className: "v-favorable" };
  if (score >= 55) return { label: "À\u00a0creuser", color: "var(--ochre)", className: "v-acreuser" };
  if (score >= 35) return { label: "Prudence", color: "var(--brick)", className: "v-prudence" };
  return { label: "Déconseillé", color: "var(--brick-deep)", className: "v-deconseille" };
};

const ScoreRing = ({ score = 73, size = 132, stroke = 6 }) => {
  const r = (size - stroke * 2) / 2;
  const c = 2 * Math.PI * r;
  const meta = verdictMeta(score);

  const [drawn, setDrawn] = React.useState(0);
  React.useEffect(() => {
    const start = performance.now();
    let raf;
    const tick = (t) => {
      const p = Math.min(1, (t - start) / 600);
      setDrawn(score * p);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [score]);

  const offset = c - (drawn / 100) * c;

  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--stone-line)" strokeWidth={stroke} />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke={meta.color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 200ms linear" }}
        />
      </svg>
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      }}>
        <div style={{
          fontFamily: "var(--font-mono)", fontWeight: 500,
          fontSize: size * 0.30, lineHeight: 1, letterSpacing: "-0.03em",
          color: "var(--ink)", fontVariantNumeric: "tabular-nums",
        }}>{Math.round(drawn)}</div>
        <div style={{
          fontFamily: "var(--font-mono)", fontSize: 10,
          color: "var(--stone)", letterSpacing: "0.06em", marginTop: 4,
        }}>/ 100</div>
      </div>
    </div>
  );
};

Object.assign(window, { ScoreRing, verdictMeta });
