import Wordmark from "../../components/design/Wordmark";
import Footer from "../../components/design/Footer";
import ScopeBadge from "../../components/design/ScopeBadge";
import PageViewBeacon from "../../components/PageViewBeacon";

export const metadata = {
  title: "La méthode locale — Cohérence (édition Metz)",
  description:
    "Comment Cohérence reconstitue le marché immobilier messin, quartier par quartier, à partir des annonces réelles — et ce que nous ne faisons délibérément pas.",
};

function Section({ eyebrow, title, children }: {
  eyebrow: string; title: string; children: React.ReactNode;
}) {
  return (
    <section style={{
      paddingTop: 32,
      borderTop: "1px solid var(--stone-line)",
      display: "flex",
      flexDirection: "column",
      gap: 12,
    }}>
      <div className="t-eyebrow">{eyebrow}</div>
      <h2 style={{
        fontFamily: "var(--font-serif)",
        fontSize: 32,
        fontWeight: 400,
        lineHeight: 1.15,
        letterSpacing: "-0.01em",
        color: "var(--ink)",
        margin: 0,
      }}>
        {title}
      </h2>
      <div style={{
        fontFamily: "var(--font-sans)",
        fontSize: 16,
        lineHeight: 1.65,
        color: "var(--ink-2)",
      }}>
        {children}
      </div>
    </section>
  );
}

export default function MethodePage() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--parchment)", color: "var(--ink)" }}>
      <PageViewBeacon name="methode_view" />
      <header style={{
        position: "sticky",
        top: 0,
        zIndex: 10,
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        background: "color-mix(in oklab, var(--parchment), transparent 20%)",
        borderBottom: "1px solid var(--stone-line)",
      }}>
        <div style={{
          maxWidth: 960,
          margin: "0 auto",
          padding: "14px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}>
          <Wordmark size={22} />
          <ScopeBadge />
        </div>
      </header>

      <main style={{ maxWidth: 720, margin: "0 auto", padding: "64px 24px 64px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 24, marginBottom: 48 }}>
          <div className="t-eyebrow">Édition Metz · notre méthode</div>
          <h1 style={{
            fontFamily: "var(--font-serif)",
            fontSize: 56,
            fontWeight: 400,
            lineHeight: 1.02,
            letterSpacing: "-0.02em",
            color: "var(--ink)",
            margin: 0,
            maxWidth: 600,
          }}>
            Une évaluation ancrée dans Metz, quartier par quartier.
          </h1>
          <p style={{
            fontFamily: "var(--font-sans)",
            fontSize: 18,
            lineHeight: 1.6,
            color: "var(--ink-2)",
            margin: 0,
            maxWidth: 560,
          }}>
            Cohérence ne se veut pas un portail national de plus. C&apos;est un second
            avis local : nous comparons votre annonce au marché réel de son secteur,
            avec la prudence d&apos;une analyse statistique objective.
          </p>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
          <Section eyebrow="Le problème" title="Le livre foncier n'est pas public">
            <p style={{ margin: 0 }}>
              En Moselle, comme en Alsace, les ventes sont inscrites au livre foncier —
              mais il n&apos;est pas librement consultable. Impossible, pour un acheteur,
              de savoir à quel prix s&apos;est réellement vendu l&apos;appartement voisin.
              Face au vendeur et à l&apos;agent, l&apos;information est asymétrique. Notre
              rôle est de réduire cet écart avec les moyens accessibles : les annonces
              du marché, lues et comparées avec méthode.
            </p>
          </Section>

          <Section eyebrow="Notre réponse" title="Reconstituer le marché du secteur">
            <p style={{ margin: 0 }}>
              Nous rassemblons les annonces réelles de Metz et de sa proche couronne,
              quartier par quartier — du Sablon à Queuleu, de Devant-les-Ponts à
              l&apos;Outre-Seille. Une médiane calculée à l&apos;échelle de la ville
              lisserait les écarts entre quartiers et tromperait. Nous descendons donc
              au niveau du secteur dès que les données le permettent.
            </p>
          </Section>

          <Section eyebrow="Comment on compare" title="Des comparables à surface proche">
            <p style={{ margin: 0 }}>
              Pour situer un prix, nous retenons les biens comparables : même secteur,
              surface proche, DPE… sur un nombre minimum de biens comparables avant de
              prononcer un écart. Nous calculons la médiane locale au m² et la position
              de votre annonce — aligné, sur-positionné, sous-positionné. Des chiffres,
              pas des adjectifs.
            </p>
          </Section>

          <Section eyebrow="La lecture" title="Trois piliers, un score sur 100">
            <p style={{ margin: "0 0 12px" }}>
              Le score de cohérence combine trois piliers :
            </p>
            <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 8 }}>
              <li><strong>Le prix</strong> (40&nbsp;points) — l&apos;écart à la médiane locale.</li>
              <li><strong>La transparence</strong> (30&nbsp;points) — l&apos;annonce est-elle claire&nbsp;? Quels signaux manquent&nbsp;?</li>
              <li><strong>Les risques</strong> (30&nbsp;points) — points d&apos;attention à creuser avant la visite.</li>
            </ul>
          </Section>

          <Section eyebrow="Nos garde-fous" title="Ce que nous ne faisons pas">
            <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 8 }}>
              <li>Nous n&apos;estimons pas un prix « juste » : nous mesurons une cohérence.</li>
              <li>Nous ne promettons pas une précision à la rue près quand la donnée
                  ne la soutient pas — l&apos;analyse reste alors à l&apos;échelle du quartier
                  ou de la ville, et le dit.</li>
              <li>Nous ne donnons pas d&apos;ordre. Nous signalons ce qui est cohérent ou
                  non&nbsp;; vous décidez.</li>
              <li>Vos analyses ne sont pas conservées.</li>
            </ul>
          </Section>

          <Section eyebrow="Le périmètre" title="Metz & Moselle, pour de vrai">
            <p style={{ margin: 0 }}>
              C&apos;est l&apos;édition Metz. La donnée, le lexique des quartiers et les
              repères sont messins — c&apos;est la condition d&apos;une évaluation
              contextualisée, donc crédible. D&apos;autres villes auront, le moment venu,
              leur propre édition, avec la même exigence locale.
            </p>
          </Section>

          <div style={{ paddingTop: 24 }}>
            <a href="/" style={{
              fontFamily: "var(--font-sans)",
              fontSize: 14,
              fontWeight: 500,
              color: "var(--brick)",
              textDecoration: "none",
            }}>
              ← Analyser une annonce
            </a>
          </div>
        </div>

        <Footer />
      </main>
    </div>
  );
}
