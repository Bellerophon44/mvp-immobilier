/**
 * Extrait la premiere URL http(s) d'un texte (payload de partage natif ou
 * collage manuel). SPEC mobile-phase2-tranche1 §5.A (AC1-AC4).
 * Cas attendus : texte + URL -> l'URL ; URL nue -> elle-meme ; plusieurs URLs
 * -> la premiere ; aucune URL -> null.
 */
export function firstUrl(_input: string): string | null {
  throw new Error('NOT_IMPLEMENTED: firstUrl');
}
