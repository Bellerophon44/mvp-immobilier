import "./globals.css";

export const metadata = {
  title: "Cohérence — Analyse d'annonces immobilières à Metz & Moselle",
  description:
    "Le livre foncier n'est pas public. Cohérence reconstitue le marché local messin, quartier par quartier, pour vérifier si le prix d'une annonce tient — avant la visite.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
