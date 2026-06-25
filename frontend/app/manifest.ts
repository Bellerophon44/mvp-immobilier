import type { MetadataRoute } from "next";

// Manifeste PWA : rend coherence-metz.fr installable sur l'ecran d'accueil
// (iPhone via "Sur l'ecran d'accueil", Android/Chrome via l'invite d'install).
// Next sert ce fichier a /manifest.webmanifest et injecte le <link rel="manifest">.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Cohérence — Analyse d'annonces immobilières",
    short_name: "Cohérence",
    description:
      "Vérifiez la cohérence d'une annonce immobilière messine — prix vs marché local, transparence, risques — avant la visite.",
    lang: "fr",
    start_url: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#F5F1EA",
    theme_color: "#F5F1EA",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
