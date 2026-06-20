import Wordmark from "./Wordmark";

export default function Footer() {
  return (
    <footer style={{
      marginTop: 96,
      paddingTop: 24,
      borderTop: "1px solid var(--stone-line)",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      flexWrap: "wrap",
      gap: 8,
      color: "var(--stone)",
      fontFamily: "var(--font-sans)",
      fontSize: 12,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Wordmark compact size={18} />
        <span>Édition Metz · Moselle</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <a href="/methode" style={{ color: "var(--ink-3)", textDecoration: "none", fontWeight: 500 }}>
          Méthode locale
        </a>
        <span>Analyses non conservées · Comparables locaux</span>
      </div>
    </footer>
  );
}
