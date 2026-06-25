import "./globals.css";
import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "Cohérence — Analyse d'annonces immobilières à Metz & Moselle",
  description:
    "Le livre foncier n'est pas public. Cohérence reconstitue le marché local messin, quartier par quartier, pour vérifier si le prix d'une annonce tient — avant la visite.",
  // PWA / iOS : ouverture plein écran depuis l'écran d'accueil + titre sous l'icône.
  // Le <link rel="manifest"> et l'apple-touch-icon sont injectés par les conventions
  // de fichier Next (app/manifest.ts, app/apple-icon.png) ; le favicon par app/icon.svg.
  appleWebApp: {
    capable: true,
    title: "Cohérence",
    statusBarStyle: "default",
  },
};

export const viewport: Viewport = {
  themeColor: "#F5F1EA",
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
