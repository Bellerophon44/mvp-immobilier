/**
 * Extrait la premiere URL http(s) d'un texte (payload de partage natif ou
 * collage manuel). SPEC mobile-phase2-tranche1 §5.A (AC1-AC4).
 * Cas attendus : texte + URL -> l'URL ; URL nue -> elle-meme ; plusieurs URLs
 * -> la premiere ; aucune URL -> null.
 */
export function firstUrl(input: string): string | null {
  const match = (input || '').match(/https?:\/\/[^\s]+/i);
  return match ? match[0] : null;
}
