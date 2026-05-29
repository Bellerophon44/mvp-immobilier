import "./globals.css";

export const metadata = {
  title: "Cohérence — Analyseur d'annonces immobilières",
  description: "Ce prix et cette annonce sont-ils cohérents avec le marché local ?",
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
