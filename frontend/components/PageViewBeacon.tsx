"use client";

import { useEffect, useRef } from "react";
import { sendEvent } from "../lib/api";

// Beacon de vue de page minimal, monte dans un server component (ex.
// methode/page.tsx) sans le passer en client : il preserve l'export `metadata`
// et le SSR/SEO. Emet un event anonyme une seule fois par montage reel — la
// garde useRef neutralise le double-mount StrictMode (dev), sinon le compteur
// de dev serait fausse. Aucune PII : un nom d'event ferme, rien d'autre.
export default function PageViewBeacon({ name }: { name: string }) {
  const sent = useRef(false);

  useEffect(() => {
    if (sent.current) return;
    sent.current = true;
    sendEvent(name);
  }, [name]);

  return null;
}
