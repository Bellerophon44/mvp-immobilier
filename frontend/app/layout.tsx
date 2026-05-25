import "./globals.css";

export const metadata = {
  title: "Analyse d'annonce immobilière",
  description:
    "Décryptez une annonce immobilière en 30 secondes : ce qui est dit, ce qui manque, ce qu'il faut vérifier.",
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
